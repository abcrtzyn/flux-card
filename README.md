# Timecard

This repo is an inter-device time card program. Designed to record clock in and clock out times using Apple shortcuts and then a program to output all of the time periods.

## Motivation

When working a student job that has very flexible hours, I needed a quick easy way to clock in and out that wasn't writing down or remembering the times. The position had instances of working a couple minutes at a time during a transition period. Later I changed this to be able to handle two jobs at the same time. The shortcuts would store that information and the Python programs would use this information.

## Requirements

These programs were designed to work on iPhone and a Mac. There are 3 Apple shortcuts: Clock in and Clock out (can run on either), and Calculate Time which directily calls Python to do the heavy lifting (can only be run on Mac). In order for both devices to have accurate inforamation, they must share a file on iCloud drive.

It should be possible to not require a Mac as long as you choose not to use the Calculate Time shortcut and have the shared file on some platform (your comupter could have access to iCloud or your iPhone could have access to some other cloud file storage).

Because the computation programs are written in Python, there is no way to easily run them on an iPhone. I would have liked this to be a self contained program, but this works good enough.

## Setup

Lots of setup steps here, please follow them carefully.

1. Create the Clock file in the location of your choice, it must be accessible by all devices you want to clock in and out with.
2. Start the file off by putting == in the top line and make sure there is no newline after it (plenty of code editors will add a newline automatically, make sure this doesn't happen)
3. On the devices which you are going to use them, import the shortcuts Clock In and Clock Out. See the README in the shortcuts folder for more information
    - Do this by opening them as files, not dragging them into the shortcuts app
    - Answer the import questions:
        - (Clock in) What jobs are you using this for (for tagging purposes)
        - Where is the Clock file located
        - (Clock out) Do you want to add descriptions
4. Setup the python environment (optional)
    - the environment allows the use of `timecard` as a shell command as a replacement for `python3 src/main.py` and that is about it.
```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```
5. Tell the script where your Clock file is located
    - right now this is hard-coded at the top of the main.py file, to be changed soon
6. Run the program using one of the following
```sh
timecard # if you have setup the python environment
python3 src/main.py
src/main.py
```

## File Format

The file I have called `Clock.txt` is the working file, where the Clock In and Clock Out shortcuts add information. The format is very simple but has some quirks.

**VERY IMPORTANT QUIRK** is that this file does not contain a final newline at the end, this is to make the shortcuts work properly. I have an idea to fix this, but it isn't an huge issue at the moment.

Line one starts with "==". This must be primed before the shortcuts are used.

If the last line of the file is "==", you are clocked out. Each clock session will fall between these lines.

A clock session looks like this
```txt
[Job]
>yyyy-mm-ddThh:mm:ss-hh:mm
<yyyy-mm-ddThh:mm:ss-hh:mm
[short description]
==
```
The times are ISO 8601 format which Shortcuts natively outputs and includes time zone information.

Short description can be multiple lines; job, in time, and out time should always be one line.


## Contributing

I'm very happy to take pull requests on this repo. If you have an output format you would like to have or any other features, feel free to submit issues or pull requests.
