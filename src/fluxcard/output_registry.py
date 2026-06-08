import io
from typing import Callable, Concatenate, Dict, List, TypeVar
from .segments import Segment

FormatterProtocol = Callable[Concatenate[io.TextIOWrapper,List[Segment],...],None]
"""A function using FormatterProtocol takes in a text io stream and an iterable of segments that are sorted by the inTime field and outputs some text
the function can also take in other options as keyword arguments."""


_OUTPUT_REGISTRY: Dict[str, FormatterProtocol] = {}

def get_function_info(func: FormatterProtocol):
        current_func_name = func.__name__
        current_func_file = func.__code__.co_filename
        current_func_line = func.__code__.co_firstlineno
        current_formatted = f'function {current_func_name} at {current_func_file}:{current_func_line}'
        return current_formatted


F = TypeVar('F', bound=FormatterProtocol)

def register_formatter(name: str) -> Callable[[F], F]:
    """Decorator to register an output format layout style."""

    def decorator(func: F) -> F:
        if name in _OUTPUT_REGISTRY:
            # can't have two functions with the same key, raise an error.
            colliding_formatted = get_function_info(_OUTPUT_REGISTRY[name])
            current_formatted = get_function_info(func)
            raise Exception(f'duplicated format name "{name}"\n- {colliding_formatted}\n- {current_formatted}')
        
        _OUTPUT_REGISTRY[name] = func
        return func

    
    return decorator


def get_formatter(name: str) -> FormatterProtocol:
    """Get the formatter specified by the string or raise an error with the valid formatters"""
    if name not in _OUTPUT_REGISTRY:
        available = ", ".join(sorted(_OUTPUT_REGISTRY.keys()))
        raise KeyError(f'unknown output format "{name}".\nAvailable formats are {available}\nSee list with more details using option --list-formats')

    return _OUTPUT_REGISTRY[name]

def print_formatters() -> None:
    print("Available Fluxcard Output Formats:")
    print("=" * 40)
    for name, func in _OUTPUT_REGISTRY.items():
        # Prints format name and the first line of its python docstring
        doc = func.__doc__.split('\n')[0] if func.__doc__ else "No description available."
        print(f"  {name:<12} ── {doc}")
