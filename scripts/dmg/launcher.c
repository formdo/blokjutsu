/* Blokjutsu.app's main executable: runs the bundled Python as `python3 -m blokjutsu`, with output appended to
   <app data>/logs/console.log. */
#include <errno.h>
#include <fcntl.h>
#include <libgen.h>
#include <limits.h>
#include <mach-o/dyld.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

static void make_dirs(char *path) {
    for (char *p = path + 1; *p; p++) {
        if (*p == '/') {
            *p = '\0';
            mkdir(path, 0755);
            *p = '/';
        }
    }
    mkdir(path, 0755);
}

static void log_to_file(void) {
    char dir[PATH_MAX];
    const char *home = getenv("BLOKJUTSU_HOME");
    if (home && *home)
        snprintf(dir, sizeof dir, "%s/logs", home);
    else
        snprintf(dir, sizeof dir, "%s/Library/Application Support/Blokjutsu.noindex/logs", getenv("HOME"));
    make_dirs(dir);
    char file[PATH_MAX];
    snprintf(file, sizeof file, "%s/console.log", dir);
    int fd = open(file, O_WRONLY | O_CREAT | O_APPEND, 0644);
    if (fd >= 0) {
        dup2(fd, STDOUT_FILENO);
        dup2(fd, STDERR_FILENO);
        close(fd);
    }
}

int main(int argc, char **argv) {
    char exe[PATH_MAX], real[PATH_MAX], python[PATH_MAX];
    uint32_t size = sizeof exe;
    if (_NSGetExecutablePath(exe, &size) != 0 || !realpath(exe, real))
        return 1;
    snprintf(python, sizeof python, "%s/../Resources/python/bin/python3", dirname(real));

    log_to_file();
    setenv("PYTHONDONTWRITEBYTECODE", "1", 1);
    setenv("PYTORCH_ENABLE_MPS_FALLBACK", "1", 1);
    unsetenv("PYTHONHOME");
    unsetenv("PYTHONPATH");

    char **args = calloc((size_t)argc + 3, sizeof *args);
    args[0] = python;
    args[1] = "-m";
    args[2] = "blokjutsu";
    for (int i = 1; i < argc; i++)
        args[i + 2] = argv[i];
    execv(python, args);
    fprintf(stderr, "Blokjutsu: cannot start %s: %s\n", python, strerror(errno));
    return 1;
}
