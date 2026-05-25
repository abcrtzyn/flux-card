# Flux Card

This repo is an inter-device time card program. Designed to record clock in and clock out times using Apple shortcuts and then a program to output all of the time periods.

## Motivation

When working a student job that has very flexible hours, I needed a quick easy way to clock in and out that wasn't writing down or remembering the times. The position had instances of working a couple minutes at a time during a transition period. Later I changed this to be able to handle two jobs at the same time. The shortcuts would store that information and the Python programs would use this information.

## Requirements

These programs were designed to work on iPhone and a Mac. There are two Apple shortcuts: Clock in and Clock out (can run on either). In order for both devices to have accurate information, they must share a file on iCloud drive.

It should be possible not to require a Mac as long as you choose not to use the Calculate Time shortcut and have the shared file on some platform (your computer could have access to iCloud or your iPhone could have access to some other cloud file storage).

Because the computation programs are written in Python, there is no way to easily run them on an iPhone. I would have liked this to be a self-contained program, but this works good enough.

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
    - The environment allows the use of shell commands `fluxcard` or `flux` as a replacement for `python3 src/main.py` and that is about it.
```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```
5. Create `config.toml` in your working folder and set your default parameters here, such as the location of the Clock file with respect to the config file or an absolute path and output timezone.
6. Run the program using one of the following
```sh
fluxcard # if you have set up the python environment
flux # if you have set up the python environment
python3 src/main.py
src/main.py
```

## CLI Interface and Macros

This section goes through details of all parameters that can be set on the command line or in config and macros config in the `config.toml` file. All options set by the command line will override the config file options. Use `fluxcard -h` for information in the command line.

### Command Line and top level config options

| Option            | CLI Flag         | Config Key        | Default / Action on not set |
| :---              | :---             | :---              | :---                        |
| **Alt Config**    | `-c [path]`      |                   | <cwd>/config.toml           |
| **Start Date**    | `[param 1]`      |                   | No minimum filter applied   |
| **End Date**      | `[param 2]`      |                   | No maximum filter applied   |
| **Print Config**  | `--print-config` |                   | Program runs in full        |
| **List Formats**  | `--list-formats` |                   | Program runs                |
| **Macro**         | `-m [macro]`     |                   | No macro used               |
| **Input File**    | `-i [path]`      | `input_file`      | *Required (Error)*          |
| **Timezone**      | `-tz [zone]`     | `output_timezone` | *Required (Error)*          |

#### Alternate Config

Alternate config file path. If you would like to have multiple configurations, this allows a quick method to switch between them. This allows for separate configuration setups. It will be useful for me and testing purposes.

- **CLI**: `-c [path]` or `--config [path]`; absolute path or path relative to cwd

#### Date Range

Filters the clocked in segments within the range specified. These are positional arguments and the only two positional arguments. Use these parameters like `fluxcard [start_date] [end_date]`. Use the format `YYYY-MM-DD`. The filter range includes `start_date` and does not include `end_date`, for the set theory people, **[...)**. Example: if you want to include periods from today, use tomorrow's date. Leaving `end_date` blank means no maximum. Leaving `start_date` blank means no minimum, you can use `_` if you want to set an end date and not a start date (such as `fluxcard _ 2026-01-01`). Leaving both out will use the whole file.

- **CLI**: positional args, thus `fluxcard [start_date] [end_date]`

#### Print Config

This option is like a dry run. It will figure out all the settings used, such as schedules for period mode, and print out the settings the program would use if you did not include this option. This is a way to check what input file the program wants to use, the output timezone, and the job and date filters before running the program.

- **CLI**: `--print-config`

#### List Formats

This option prints the available output formats and the top line of their docstring and then exits.

- **CLI**: `list-formats`

#### Macros

Read more about macros in the [macro section](#macros-and-macro-options). The `-m [macro]` option lets you set the macro to use.

- **CLI**: `-m [macro]` or `--macro [macro]`

#### Timecard File

The Clock file to input data from. This parameter is required. If specified in both command line and config, the command line parameter will be used.

- **CLI**: `-i [path]` or `--input [path]`; absolute path or path relative to cwd.
- **Config**: `timecard_path = path/to/Clock.txt`; absolute path or path relative to the config file directory

#### Output Timezone

Timezone to convert all clock times to. Accepts standard IANA identifiers (like `America/Chicago`). The timezone allows the program to handle daylight savings and calculate hours across timezones. If specified in both command line and config, the command line parameter will be used.

- **CLI**: `-tz [zone]` or `--timezone [zone]`
- **Config**: `output_timezone = "America/Chicago"`

### Macros and macro options

| Option          | CLI Flag             | Config Key    | Macro Key    |Default / Action on not set       |
| :---            | :---                 | :---          | :---         | :---                             |
| **Job Filter**  | `-j [names]`         | `default_job` | `job_filter` | *No filter applied*              |
| **Period Mode** | `-p [index]`         | *N/A*         | `period`     |                                  |
| **Output**      | `-o [dest] [format]` | *N/A*         | `outputs`    | *Required (no error, no output)* |

#### Job Filter

Job(s) to filter all clock in sessions. Must be the exact same as what is on the top line of each section and must not be `_`.

If you have only one job you are calculating for, you can set the `default_job` that way it will always be set. This only allows a single string.

In macros, `job_filter` can be a string (single job) or a list of strings. `job_filter = "name"` and `job_filter = ["name1","name2"]` are allowed. Macro setting overrides config level setting.

On the command line, all of `-j name`, `-j name1,name2` or `-j "name1, name2"` are valid. Command line overrides both config and macro settings. If you want to override the setting on the command line back to no filter, use `-j _`.

- **CLI**: `-j [names]` or `--job [names]`
- **Macros**: `job_filter = "name"` or `job_filter = ["name1","name2"]` 
- **Config**: `default_job = "name"`

#### Period Mode

Read more about using period mode in the [period mode section](#period-mode-1). This must be an integer value.

- **CLI**: `-p [index]` or `--period [index]`
- **Macros**: `period = 1`

#### Output

Tell the program to output to a destination (stdout or file path) with a given format function. `dest` can be `stdout` or a file path. When specifying in a macro, `dest` can be left out to select `stdout` or specified explicitly. Many output formats are supported, and you can propose or create your own. See [output formats](#output-formats). The command line only allows one output flag, macros allow for multiple outputs at once. Many output formats also have options to customize the output, these can vary from format to format. I've used `param` as an example below. Currently output specific params are not allowed on the command line.

- **CLI**: `-o [dest] [format]` or `--output [dest] [format]` (dest file path absolute or relative to cwd)
- **Macros**: `outputs = [{dest="path/to/file.txt",format="form",param=true}]` (dest file path absolute or relative to config file directory)

#### Macros example

A macro should be defined in a config file using the following format.
Run this macro on the command line as `fluxcard -m macro-name`.
```toml
[macros.macro-name]
job_filter = "job_name"
# also allowed
# job_filter = ["job1","job2"]
period = 1
outputs = [
    { dest = "stdout", format = "total" },
    { dest = "/abs/path/to/summary.txt", format = "summary" },
    { dest = "invoice.txt", format = "card" }
]
```


## Period Mode

Period mode calculates start and end dates based on pay schedules. Use the `-p [index]` command line option or `period` key in macros to switch to period mode. Because this mode calculates a start and end date, you must not also set a start date or end date filter on the command line. Also, setting a job filter in the macro or on the command line is required in this mode (even if that filter contains every job). Every job in the filter must be attached to the same schedule, otherwise period mode wouldn't know which schedule to follow.

Period mode takes an integer as a period offset relative to today. Examples are easiest to show. A period index 0 would be the pay period that includes today, the *current* period. A period index 1 would be the *previous* pay period. Any integer is allowed (even negative numbers for future periods if you really need that).

To get period mode working, you must create a schedule in the config and assign that schedule to one or multiple jobs. Create a schedule like the example below. Every schedule has to have a name, in this case `example`, and a type. From there, each schedule type has its own parameters. See each schedule's details further down.

```toml
[schedules.example]
type = "days_cycle"
period_anchor = 2026-05-10
period_length = 14
```

Next you have to assign this schedule to a job like this. A schedule can be assigned to more than one job.

```toml
[jobs.name]
schedule = "example"
```

### Schedules

There are multiple schedules available, this section details each one and its purpose.

#### Days Cycle

Days cycle is the first schedule made. It accounts for any period cycle that is an exact number of days. The most common being weekly and bi-weekly. The parameters are `period_anchor` which is the date of the first day of a period cycle, and `period_length` which is the length of the period in days.

```toml
[schedules.example]
type = "days_cycle"
period_anchor = 2026-05-10 # in YYYY-MM-DD
period_length = 14 # an integer
```

#### Monthly Cycle

Monthly cycle handles cases where the period cycle begins on the nth day of each month. The parameter is `start_day` which can be an integer between 1 and 28 inclusive.

```toml
[schedules.example]
type = "monthly"
start_day = 18
```

#### Manual Cycle

The manual cycle is for just manual tracking applications or cases where you just need to submit a timecard anytime. Rather than having to remember the date you submitted the last set of times, you can enter these dates into the config file. There are future plans to have the program add these dates automatically, but for now, just add them to a `manual_schedule_history.schedule_name` section manually. Remember that these markers should be the start date of each period, not the end date.

```toml
[schedules.example]
type = "manual"
```

Example manual schedule markers list. Must be a list of dates in sorted order.

```toml
[manual_schedule_history.example]
markers = [
    2025-03-01,
    2025-05-29,
    2025-08-18
]
```


## Output Formats

Not documented yet.


## Program documentation

### File Format

The file I have called `Clock.txt` is the working file, where the Clock In and Clock Out shortcuts add information. The format is very simple but has some quirks.

**VERY IMPORTANT QUIRK** is that this file does not contain a final newline at the end. This is to make the shortcuts work properly. I have an idea to fix this, but it isn't a huge issue at the moment.

Line one starts with "==". This must be primed before the shortcuts are used.

If the last line of the file is "==", you are clocked out. Each clock session will fall between these lines.

A clock session looks like this:
```txt
[Job]
>yyyy-mm-ddThh:mm:ss-hh:mm
<yyyy-mm-ddThh:mm:ss-hh:mm
[short description]
==
```
The times are ISO 8601 format, which Shortcuts natively outputs and includes time zone information.

Short description can be multiple lines; job, in time, and out time should always be one line.


## Contributing

I'm very happy to take pull requests on this repo. If you have an output format you would like to have or any other features, feel free to submit issues or pull requests.
