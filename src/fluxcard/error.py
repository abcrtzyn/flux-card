import sys


class FluxCardError(Exception): """Exceptions that a user should see, not a crash"""
class FluxCardInputError(FluxCardError): """Expections for all data validation and parsing"""

class FluxCardFieldRequiredError(FluxCardInputError): 
    """Exceptions when a field is required in config or command line"""
    # field: str
    # cli_flag: str
    # config_option: str


class FluxCardConfigError(FluxCardInputError): """Exceptions that occur when parsing a config file"""
class FluxCardConfigTypeError(FluxCardConfigError): """Wrong type, could not parse"""
class FluxCardConfigValueError(FluxCardConfigError): """Correct type, but invalid value"""
# class FluxCardConfigFieldRequiredError(FluxCardConfigError): """Correct type, but invalid value"""

class FluxCardCommandLineError(FluxCardInputError): """Could not parse the command line arguments"""

class FluxCardRuntimeError(FluxCardError): """Errors that happen during the actual running of the program, unlikely."""


def print_terminal_error(e: FluxCardError) -> None:
    """Formats and prints beautiful, traceback-free error messages."""
    # Visual anchors (Use ANSI escape codes for color if not using 'rich')
    RED = "\033[91m\033[1m"
    YELLOW = "\033[93m"
    RESET = "\033[0m"
    BOLD = "\033[1m"

    print(f"\n{RED}✕ Error:{RESET} ", file=sys.stderr, end="")

    if isinstance(e, FluxCardConfigTypeError):
        print(f"{BOLD}Invalid type in config{RESET}", file=sys.stderr)
    elif isinstance(e, FluxCardConfigValueError):
        print(f"{BOLD}Invalid value in config{RESET}", file=sys.stderr)
    elif isinstance(e, FluxCardFieldRequiredError):
        print(f"{BOLD}Missing required value in input{RESET}", file=sys.stderr)
    elif isinstance(e, FluxCardConfigError):
        print(f"{BOLD}Error in config{RESET}", file=sys.stderr)
    elif isinstance(e, FluxCardCommandLineError):
        print(f"{BOLD}Failed to parse command line arguments{RESET}", file=sys.stderr)
    elif isinstance(e, FluxCardInputError):
        print(f"{BOLD}Error in input parsing and validation{RESET}", file=sys.stderr)
    elif isinstance(e, FluxCardRuntimeError):
        print(f"{BOLD}Error in program execution{RESET}", file=sys.stderr)

    # Print the core error message
    print(f"  {e}", file=sys.stderr)

    if isinstance(e, FluxCardConfigError):
        print('\nError occured in this config location:')

        # print out a config file tracebac
        if hasattr(e,'__notes__'):
            notes = reversed(e.__notes__)
            print(f'{YELLOW}{next(notes)}{RESET}',file=sys.stderr)
            print(f'{YELLOW}{' ➔ '.join(notes)}{RESET}',file=sys.stderr)
        
    # # Extract and format the add_note() breadcrumbs
    # if hasattr(e, "__notes__") and e.__notes__:
    #     # Reverse them if you want a top-down path: config -> schedule -> type
    #     crumbs = " ➔ ".join([note.replace("at key ", "") for note in e.__notes__])
    #     print(f"  {YELLOW}Location:{RESET} config.{crumbs}", file=sys.stderr)
        
    print(file=sys.stderr) # Clean trailing spacing
