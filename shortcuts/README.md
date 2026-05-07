# Shortcuts

This folder contains the shortcuts needed for this repo. This readme will explain what each of the shortcuts do, and explains details of the setup process.

## Setup details

The best way to import shortcuts from file is by opening them like normal files. This can be done on Mac or iPhone. It will take you to the shortcuts app and ask the import questions.

Important: Do not click and drag the shortcut file into shortcuts, it will not ask the import questions.

If you have your shortcuts sharing between devices, you will only need to import the shortcuts on one device.

## Clock In

### Setup questions

Clock In will ask you what jobs you want to track. If you have more than one, fill in the full list. If only one job is present in the list, it will not ask.

It will ask what folder the Clock file is in as well as the file name. This is due to the bad choice that append text to file requires a folder path and file name/path. This is my compromise.

### Explanation

First things are the setup variables, list of jobs (editable here), the count of jobs calculated at run time. The jobs are the tags that go in each clock in session.

Then the file folder and file name.

Next is to figue out if there is currently a clocked in section. It gets the file, splits it into lines.

If the last line of the file is "==", you are not clocked in and the shortcut can continue into the if statement. Otherwise, it reports that you are clocked in already and ends without modification.

Inside the if statement, if there is more than one job in the list, ask for a selection from the list. Otherwise, just take the first (and only) job.

Then ask for the date time to clock in at. This will always default to the current time, so just pressing "Done" will use the current time, hence the "(now)" when prompted. Note that some devices mark this time down to the seconds, others only to the minute. If you need to change when you clock in, edit the time to what you need before hitting done.

Once all the information is gathered, add it all to the file.

It adds new line with the job selected and a new line with the time in and finishes.

## Clock In

### Setup questions

Clock Out will ask what folder the Clock file is in as well as the file name. This is due to the bad choice that append text to file requires a folder path and file name/path. This is my compromise.

It will then ask you want to record short descriptions of the work done. This information is always optional and can give you a sense of how long a task took or maybe you have another purpose in mind. If you choose no, you will never be prompted to enter this information. If you choose yes, you can choose to write it or skip it.

### Explanation

First things are the setup variables, the file folder and file name.

The same as clock in, it grabs the file text, splits it into lines.

If the last line of the file is not "==", you are clocked in and the shortcut can continue into the if statement. Otherwise, it will report that you are not clocked in and end without modification.

If you are clocked in, it continues to do a couple of setup things. First is to get the second to last line of the file, which is the job specified from Clock In. The shortcut then asks for the Clock Out date and time. Again, default date time is now, so just pressing "Done" will use that. The job is shown so you can be sure you have done things correctly.

If in the setup questions you have specified to include a short description, the shortcut will prompt for this information, otherwise is will just leave a blank line.

Once all this information is specified, all of it is added to the file. All on new lines, the out time is added, the short description, and lastly the end of section marker "==" to signal that you are not clocked in.

