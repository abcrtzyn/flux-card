# Flux Card

This repo is an inter-device time card program. Designed to record clock in and clock out times using Apple shortcuts and then a program to output all of the time periods.

## Motivation

When working a student job that has very flexible hours, I needed a quick easy way to clock in and out that wasn't writing down or remembering the times. The position had instances of working a couple minutes at a time during a transition period. Later I changed this to be able to handle two jobs at the same time. The shortcuts would store that information and the Python programs would use this information.

## Requirements

These programs were designed to work on iPhone and a Mac. There are 2 Apple shortcuts: Clock in and Clock out (can run on either). In order for both devices to have accurate inforamation, they must share a file on iCloud drive.

It should be possible to not require a Mac as long as you choose not to use the Calculate Time shortcut and have the shared file on some platform (your comupter could have access to iCloud or your iPhone could have access to some other cloud file storage).

Because the computation programs are written in Python, there is no way to easily run them on an iPhone. I would have liked this to be a self contained program, but this works good enough.

## Setup

Lots of setup steps here, please follow them carefully.

1. Create the Clock file in the location of your choice, it must be accessible by all devices you want to clock in and out with.
2. Start the file off by putting `==` in the top line and make sure there is no newline after it (plenty of code editors will add a newline automatically, make sure this doesn't happen)
3. On the devices which you plan to clock in and out, import the shortcuts Clock In and Clock Out. See the README in the shortcuts folder for more information
    - Do this by opening them as files, not dragging them into the shortcuts app
    - Answer the import questions:
        - (Clock in) What jobs are you using this for (for tagging purposes)
        - Where is the Clock file located
        - (Clock out) Do you want to add descriptions
4. Setup the python environment (optional)
    - the environment allows the use of shell commands `fluxcard` or `flux` as a replacement for `python3 src/main.py` and that is about it.
```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```
5. Create `config.toml` and set your default parameters here, such as the location of the Clock file with respect to the config file (repo root) or an absolute path and output timezone. Use [`config_example.toml`](config_example.toml) as an example. See [config file options](#options)
6. Run the program using one of the following
```sh
fluxcard # if you have set up the python environment
flux # if you have set up the python environment
python3 src/main.py
src/main.py
```

## Options

This section goes through details of all parameters that can be set on the command line or in the `config.toml` file. All options set by the command line will override the config file options. Use `fluxcard -h` for information in the command line.

| Option | CLI Flag | Config Key | Default / Fallback **date** mode | Default / Fallback **period** mode |
| :--- | :--- | :--- | :--- | :--- |
| **Input File** | `-i [path]` | `input_file` | *Error (Required)* | *Error (Required)* |
| **Timezone** | `-tz [zone]` | `output_timezone` | *Error (Required)* | *Error (Required)* |
| **Alt Config** | `-c [path]` | *N/A* | *\<repo root\>/config.toml* | *\<repo root\>/config.toml* |
| **Job** | `-j [name]` | `job_filter` in macro and `default_job` | *No filter applied* | *Error (Required)* |
| **Start Date** | `[param 1]` | *N/A* | *No minimum filter applied* ||
| **End Date** | `[param 2]` | *N/A* | *No maximum filter* ||
| **Period Mode** | `-p [index]` | `period` in macro |||
| **Period Anchor**| `--period-settings [anchor] [length]` | `period_anchor` in job || *Error (Required)* |
| **Period Length**| `--period-settings [anchor] [length]` | `period_length` in job || *Error (Required)* |
| **Output** | `-o [dest] [format]` | `outputs` in macro | *Required (no error, no output)* | *Required (no error, no output)*| 
| **Macro** | `-m [macro]` | *N/A* |||
| **Print Config** | `--print-config` | *N/A* |||


#### Timecard File

The Clock file to input data from. This parameter is required.

- **CLI**: `-i [path]` or `--input [path]`; absolute path or path relative to cwd.
- **Config**: `timecard_path`; absolute path or path relative to the config file directory

#### Output Timezone

Timezone to convert all clock times to. Accepts standard IANA identifiers (like `America/Chicago`). The timezone allows the program to figue out daylight savings or calculating hours across timezones.

- **CLI**: `-tz [zone]` or `--timezone [zone]`
- **Config**: `output_timezone`

#### Alternate Config

Alternate config file path. If you would like to have multiple configurations, this allows a quick method to switch between them. This would allow a seperate configuration setups for output formats or a different input file, among other things.

- **CLI**: `-c [path]` or `--config [path]`; absolute path or path relative to cwd

#### Job

Job to filter all clock in sessions. Must be the exact same as what is on the top line of each section. Required by period mode. If you have only one job you are calculating for, you can set the `default_job` that way it will always be set. You can also set job filters in macros using `job_filter`. On the commind line, if you want to override config job filters, use `-j _` as the command line option.

- **CLI**: `-j [name]` or `--job [name]`
- **Config**: `default_job`
- **Macros**: `job_filter` [(see macro section)](#macros)

#### Date Range

Only available on the CLI, filters the clocked in segments within the range specified. Use the format `YYYY-MM-DD`. The filter range includes `start_date` and does not include `end_date`, for the set theory people, **[...)**. Example: if you want to include periods from today, use tomorrow's date. Leaving `end_date` blank means no maximum. Leaving `start_date` blank means no minimum, you can use `_` if you want to set an end date and not a start date (such as `fluxcard _ 2026-01-01`). Leaving both out will use the whole file.

- **CLI**: positional args, thus `fluxcard [start_date] [end_date]`

#### Period Mode

Filters based on a period pay schedule, with the options period anchor and period length set, you can enter a period offset relative to today and it will filter in that range. The period offset works as follows. Use 0 for the *current* period (the pay period that today is a part of), use 1 for the *previous* pay period, or any other integer for whatever you are looking for. This mode will use the anchor and period length to figue out when the period starts and ends and filter based on those dates. You can set a period filter in a macro using `period` key.

- **CLI**: `-p [index]` or `--period [index]`
- **Macros**: `period` [(see macro section)](#macros)


#### Period Anchor

The anchor point for period mode, the first day in of a pay period. Can be set to any date past or future. Is set per job in config.

- **CLI**: `--period-settings [anchor] [length]`
- **Config**: `[jobs.name] period_anchor`

#### Period Length

The length of a pay period measured in days. Used in period mode. Is set per job in config.

- **CLI**: `--period-settings [anchor] [length]`
- **Config**: `[jobs.name] period_length`

#### Print Config

Simple option that does all the config resolution, from config file and command line arguments, prints the settings and exits. No input, processing, or output is done. Could be useful to see what configuration you are running at the moment, which input file, what timezone, etc.

Note that period settings are resolved into filter start and end date.

- **CLI**: `--print-config`

## Output

Tell the program to output to a destination (stdout or file path) with a given format function. `dest` can be `stdout` or a file path. When specifing in a macro, `dest` can be left out to select `stdout` or specified explicitly.

- **CLI**: `-o [dest] [format]` or `--output [dest] [format]` (dest file path absolute or relative to cwd)
- **Macros**: `outputs` [(see macro section)](#macros) (dest file path absolute or relative to config file directory)



## Macros

Macros allow short commands to run commonly used functions. Macros can be defined in a config file to do job filter, period mode, and multiple outputs at once to files and out to the terminal. Macros are only defined in config files, you can not choose one to run in the config file.

- **CLI**: `-m [macro]` or `--macro [macro]`


## Program documentation

### File Format

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
