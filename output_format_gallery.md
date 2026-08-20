# Output Format Gallery

The output formats that are available in the standard library and their parameters. Note in brackets is the actual output format specifier.

## Timecard [card]

Designed to be copy and pasted in to a well structured word document to print off a time card. The first tab is the date, second tab is the in time, third tab is the out time, fourth is the hours. At the bottom is a horizontal line and a total number of hours (also in the 4th tab space).

Parameters: This function has no parameters
<!-- | name | type | default | description |
| :--- | :--- | :---    | :---        | -->


```txt
	In	Out	Hours
Mon, Feb 10 2025
	9:15 AM	12:30 PM	3:15:00
Fri, Feb 14 2025
	8:30 AM	11:45 AM	3:15:00
	1:15 PM	2:30 PM	1:15:00
	7:00 PM	8:15 PM	1:15:22
Tue, Feb 25 2025
	1:10 PM	5:25 PM	4:15:00
Wed, Mar 12 2025
	10:00 AM	11:45 AM	1:45:00
Wed, Mar 19 2025
	3:00 PM	4:20 PM	1:20:00
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total			16:20:22
```

## CSV [csv]

Outputs a CSV with columns date, in time, out time, elapsed time, job, and the description given.

Parameters:
| name | type | default | description |
| :--- | :--- | :---    | :---        |
| job_column | bool | True | whether to include the job column. Useful to disable if you only have one job |

```csv
date,in,out,elapsed,job,description
2025-02-10,9:15:00AM-0600,12:30:00PM-0600,3:15:00,WebDev,"Fix database connection timeout error and update plugins"
2025-02-14,8:30:00AM-0600,11:45:00AM-0600,3:15:00,WebDev,"Morning coding session - implement new dashboard layout"
2025-02-14,1:15:00PM-0600,2:30:00PM-0600,1:15:00,WebDev,"Afternoon sync meeting with engineering team and review PRs"
2025-02-14,7:00:00PM-0600,8:15:22PM-0600,1:15:22,WebDev,"Late evening hotfix deployment - patch critical checkout bug"
2025-02-25,1:10:00PM-0600,5:25:00PM-0600,4:15:00,WebDev,"Refactor user authentication flow and test login edge cases"
2025-03-12,10:00:00AM-0500,11:45:00AM-0500,1:45:00,WebDev,"Deploy staging build to production and verify SSL certificates"
2025-03-19,3:00:00PM-0500,4:20:00PM-0500,1:20:00,WebDev,"Optimize image assets and patch mobile CSS layout bugs"
```

## Summary [summary]

Outputs a nice text format time card. For each day worked, the total time on that day is shown as well as each clock in time, time worked, and description for each segment.

Parameters: This function has no parameters
<!-- | name | type | default | description |
| :--- | :--- | :---    | :---        | -->

```txt
Mon, Feb 10 2025   3:15:00
  9:15:00AM-0600     3:15:00   Fix database connection timeout error and update plugins
Fri, Feb 14 2025   5:45:22
  8:30:00AM-0600     3:15:00   Morning coding session - implement new dashboard layout
  1:15:00PM-0600     1:15:00   Afternoon sync meeting with engineering team and review PRs
  7:00:00PM-0600     1:15:22   Late evening hotfix deployment - patch critical checkout bug
Tue, Feb 25 2025   4:15:00
  1:10:00PM-0600     4:15:00   Refactor user authentication flow and test login edge cases
Wed, Mar 12 2025   1:45:00
 10:00:00AM-0500     1:45:00   Deploy staging build to production and verify SSL certificates
Wed, Mar 19 2025   1:20:00
  3:00:00PM-0500     1:20:00   Optimize image assets and patch mobile CSS layout bugs
```

## Total [total]

Simply outputs the total hours in H:mm:ss

Parameters: This function has no parameters
<!-- | name | type | default | description |
| :--- | :--- | :---    | :---        | -->

```txt
16:20:22
```


## Visualization [visualization]

Outputs a terminal visualization showing roughly the hours worked in a graphical style. Filled in boxes show hours worked.




Parameters:
| name | type | default | description |
| :--- | :--- | :---    | :---        |
| fill_in | bool | True | If True, will fill in all dates from start to end. If False, will only show days with hours |
| use_date_filter | bool | False | If False, will find the min and max days and use that range. If True, will use the filter start and end dates if they are set (includes period calculations) |

```txt
Mon, Feb 10 2025: ░░░░░░░░░████░░░░░░░░░░░ (Total: 3.25h)
Tue, Feb 11 2025: ░░░░░░░░░░░░░░░░░░░░░░░░ (Total: 0h)
Wed, Feb 12 2025: ░░░░░░░░░░░░░░░░░░░░░░░░ (Total: 0h)
Thu, Feb 13 2025: ░░░░░░░░░░░░░░░░░░░░░░░░ (Total: 0h)
Fri, Feb 14 2025: ░░░░░░░░████░██░░░░██░░░ (Total: 5.76h)
Sat, Feb 15 2025: ░░░░░░░░░░░░░░░░░░░░░░░░ (Total: 0h)
Sun, Feb 16 2025: ░░░░░░░░░░░░░░░░░░░░░░░░ (Total: 0h)
Mon, Feb 17 2025: ░░░░░░░░░░░░░░░░░░░░░░░░ (Total: 0h)
Tue, Feb 18 2025: ░░░░░░░░░░░░░░░░░░░░░░░░ (Total: 0h)
Wed, Feb 19 2025: ░░░░░░░░░░░░░░░░░░░░░░░░ (Total: 0h)
Thu, Feb 20 2025: ░░░░░░░░░░░░░░░░░░░░░░░░ (Total: 0h)
Fri, Feb 21 2025: ░░░░░░░░░░░░░░░░░░░░░░░░ (Total: 0h)
Sat, Feb 22 2025: ░░░░░░░░░░░░░░░░░░░░░░░░ (Total: 0h)
Sun, Feb 23 2025: ░░░░░░░░░░░░░░░░░░░░░░░░ (Total: 0h)
Mon, Feb 24 2025: ░░░░░░░░░░░░░░░░░░░░░░░░ (Total: 0h)
Tue, Feb 25 2025: ░░░░░░░░░░░░░█████░░░░░░ (Total: 4.25h)
Wed, Feb 26 2025: ░░░░░░░░░░░░░░░░░░░░░░░░ (Total: 0h)
Thu, Feb 27 2025: ░░░░░░░░░░░░░░░░░░░░░░░░ (Total: 0h)
Fri, Feb 28 2025: ░░░░░░░░░░░░░░░░░░░░░░░░ (Total: 0h)
Sat, Mar 01 2025: ░░░░░░░░░░░░░░░░░░░░░░░░ (Total: 0h)
Sun, Mar 02 2025: ░░░░░░░░░░░░░░░░░░░░░░░░ (Total: 0h)
Mon, Mar 03 2025: ░░░░░░░░░░░░░░░░░░░░░░░░ (Total: 0h)
Tue, Mar 04 2025: ░░░░░░░░░░░░░░░░░░░░░░░░ (Total: 0h)
Wed, Mar 05 2025: ░░░░░░░░░░░░░░░░░░░░░░░░ (Total: 0h)
Thu, Mar 06 2025: ░░░░░░░░░░░░░░░░░░░░░░░░ (Total: 0h)
Fri, Mar 07 2025: ░░░░░░░░░░░░░░░░░░░░░░░░ (Total: 0h)
Sat, Mar 08 2025: ░░░░░░░░░░░░░░░░░░░░░░░░ (Total: 0h)
Sun, Mar 09 2025: ░░░░░░░░░░░░░░░░░░░░░░░░ (Total: 0h)
Mon, Mar 10 2025: ░░░░░░░░░░░░░░░░░░░░░░░░ (Total: 0h)
Tue, Mar 11 2025: ░░░░░░░░░░░░░░░░░░░░░░░░ (Total: 0h)
Wed, Mar 12 2025: ░░░░░░░░░░██░░░░░░░░░░░░ (Total: 1.75h)
Thu, Mar 13 2025: ░░░░░░░░░░░░░░░░░░░░░░░░ (Total: 0h)
Fri, Mar 14 2025: ░░░░░░░░░░░░░░░░░░░░░░░░ (Total: 0h)
Sat, Mar 15 2025: ░░░░░░░░░░░░░░░░░░░░░░░░ (Total: 0h)
Sun, Mar 16 2025: ░░░░░░░░░░░░░░░░░░░░░░░░ (Total: 0h)
Mon, Mar 17 2025: ░░░░░░░░░░░░░░░░░░░░░░░░ (Total: 0h)
Tue, Mar 18 2025: ░░░░░░░░░░░░░░░░░░░░░░░░ (Total: 0h)
Wed, Mar 19 2025: ░░░░░░░░░░░░░░░██░░░░░░░ (Total: 1.33h)
```
