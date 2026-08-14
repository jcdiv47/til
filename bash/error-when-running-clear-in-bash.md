# Error When Running clear in Bash

I encoutered the following error when I ssh into a really dated ubuntu server(1804 for crying out loud) and run the `clear` command:

```bash
~$ clear
terminals database is inaccessible
```

`clear` relies on the ncurses "terminfo" database. This error means Ubuntu can't locate or read that database—often because TERMINFO is misconfigured or ncurses-term is missing.

The following commands works so I put them at the end of `~/.bashrc`.

```bash
unset TERMINFO TERMINFO_DIRS
export TERM=xterm-256color
clear
```

> [!NOTE]
>  If the above works, remove any TERMINFO or TERMINFO_DIRS assignments from ~/.bashrc, ~/.profile, or ~/.zshrc.

