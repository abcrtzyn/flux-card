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

