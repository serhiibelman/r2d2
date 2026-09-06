from colorama import Fore, Style


def colored_print(message, color):
    print(f"{color}{message}{Style.RESET_ALL}")


def print_info(msg):
    colored_print(msg, Fore.BLUE)


def print_success(msg):
    colored_print(msg, Fore.GREEN)


def print_warning(msg):
    colored_print(msg, Fore.YELLOW)


def print_error(msg):
    colored_print(msg, Fore.RED)
