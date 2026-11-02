# Adapted from MOSS-Image (https://github.com/OpenMOSS/MOSS-Image): the forward pass of MOSSImageTransformer
# in the pipeline code published with the MOSS-Image model weights. Copyright the OpenMOSS Team; licensed under the
# Apache License, Version 2.0 (see LICENSE and NOTICE).
#
# Changes from the original: sinusoidal time features are computed in float32 (MPS has no float64); RoPE and the
# text projection are cached per image and matched by tensor contents; layers listed in skip_layers are skipped.
"""Replacement forward for the MOSS-Image transformer, used on Apple silicon (MPS)."""
from __future__ import annotations


def mps_transformer_forward(self, hidden_states, timestep, encoder_hidden_states, mask, skip_layers=None):
    """MOSS transformer forward with float32 (not float64) sinusoidal time features, which MPS requires.

    RoPE and the text projection depend only on (prompt embedding, size), not on the timestep, so they are
    computed once per generation and reused across all steps; reset_step_cache() clears them per image.
    """
    import torch
    from diffusers.models.modeling_outputs import Transformer2DModelOutput

    skip_layers = skip_layers or ()
    batch, _, height, width = hidden_states.shape
    times = timestep
    if not torch.is_tensor(times):
        times = torch.tensor([times], dtype=hidden_states.dtype, device=hidden_states.device)
    elif times.ndim == 0:
        times = times[None]
    half = self.time_embedding[0].weight.shape[1] // 2
    freq = 10000 ** (-torch.arange(half, device=times.device, dtype=torch.float32) / half)
    phase = times.float()[:, None] * freq
    embedding = torch.cat((phase.cos(), phase.sin()), -1)
    time = self.time_embedding(embedding.to(self.time_embedding[0].weight.dtype)).float()
    mod = self.shared_block_modulation(time.to(self.shared_block_modulation.weight.dtype)).view(batch, 6, -1)
    head = self.video_head_modulation(time.to(self.video_head_modulation.weight.dtype)).view(batch, 2, -1)
    outputs = []
    for index in range(batch):
        context = encoder_hidden_states[index:index + 1, mask[index].bool()]
        if context.shape[1] == 0:
            raise ValueError("Each sample needs at least one valid text token.")
        video = hidden_states[index:index + 1].flatten(2).transpose(1, 2)
        video = self.video_embedder(video.to(self.video_embedder.weight.dtype).contiguous())
        rope, text = _rope_and_text(self, encoder_hidden_states, index, context, height, width, video.dtype)
        x = torch.cat((video, text), 1)
        for layer_index, layer in enumerate(self.layers):
            if layer_index not in skip_layers:
                x = layer(x, rope, mod[index:index + 1])
        x = self.final_norm_video(x[:, :height * width].to(self.final_norm_video.weight.dtype))
        x = x * (1 + head[index:index + 1, 1, None]) + head[index:index + 1, 0, None]
        x = self.final_linear_video(x.to(self.final_linear_video.weight.dtype))
        outputs.append(x.transpose(1, 2).reshape(1, -1, height, width))
    return Transformer2DModelOutput(sample=torch.cat(outputs))


def _rope_and_text(self, encoder_hidden_states, index, context, height, width, dtype):
    """Reuse RoPE and the text projection for a context seen earlier in this image.

    Matched by value (torch.equal), never by tensor address: the allocator can hand a freed address to a
    different prompt's tensor of the same shape, which would silently swap cond and uncond text.
    """
    import torch

    entries = self.__dict__.setdefault("_step_cache", [])
    for ctx, h, w, rope, text in entries:
        if (h, w) == (height, width) and ctx.shape == context.shape and torch.equal(ctx, context):
            return rope, text
    rope = self.rope(height, width, context.shape[1], encoder_hidden_states.device).to(dtype)
    text = self.text_embedder(context, rope[:, height * width:])
    entries.append((context, height, width, rope, text))
    del entries[:-4]
    return rope, text


def reset_step_cache(transformer):
    transformer.__dict__["_step_cache"] = []
