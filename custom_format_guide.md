# Custom Format Guide

Format functions are functions that take in a file as a TextIOWrapper and a list of segment data. Write out text to the file, it could be stdout or a file.

### Data
The data parameter is a list of Segments. This data is sorted by the *Clock In Time*, which seems to be the most used sort needed.

#### Segment class

The Segment class represents one clocked in segment, it contains a job (empty string if not given), a clock in and out time, description if given (empty if not given) and the calculated elapesed time. All in and out times will be in the specified output timezone.

```python
@dataclass
class Segment:
    job: str
    inTime: datetime
    outTime: datetime
    description: str
    elapsed: timedelta
```

## Setup instructions

1. Create a python file
2. Add the python file as an output plugin to your config file. Can be absolute path or relative to the config file.
```toml
output_plugins = ["filename.py"]
```
3. Define and register your function. In your python file, make sure to import the register formatter decorator. Set the name you want to use as the parameter of register_formatter. Example below. A type checker can tell you if your function has the correct type.
```python
from fluxcard.output_registry import register_formatter
from fluxcard.segments import Segment

@register_formatter("custom_name")
def custom_function(file: TextIOWrapper, data: List[Segment]):
```
4. Use it! The fluxcard program will log that your module is loaded and new formatters were registered. If the name is taken already, the program will error. You can use the `--list-formats` to see if yours shows up.

## Other Parameters

Your functions can take more parameters.

After the first two parameters, you can have any other settings arguments you want. You must pass them into macro output config exactly the names specified by the function. Suggestion, always set a default value for each of these extra parameters. You can also use **kwargs parameter in complex situations which avoids all before run parameter checking.

## Processing functions

There are many useful functions that I think are comon enough that I have impletemented them in fluxcard.processers library. Manually documeneting all of them would be hard for me, so for now, take a look through the code if you wish to use them.

