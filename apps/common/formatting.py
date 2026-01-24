from colorama import Fore, Style


def print_info(message):
    print(Fore.BLUE, f"{message}", Style.RESET_ALL)


def print_warning(message):
    print(Fore.YELLOW, f"{message}", Style.RESET_ALL)


def print_error(message):
    print(Fore.RED, f"{message}", Style.RESET_ALL)
