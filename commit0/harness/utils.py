import getpass
import hashlib
import requests


class EvaluationError(Exception):
    def __init__(self, repo, message, logger):
        super().__init__(message)
        self.super_str = super().__str__()
        self.repo = repo
        self.log_file = logger.log_file
        self.logger = logger

    def __str__(self):
        return (
            f"Evaluation error for {self.repo}: {self.super_str}\n"
            f"Check ({self.log_file}) for more information."
        )


def get_ip():
    try:
        response = requests.get('https://api.ipify.org?format=json')
        response.raise_for_status()
        public_ip = response.json()['ip']
        return public_ip
    except requests.RequestException as e:
        return f"Error: {e}"


def get_user():
    return getpass.getuser()


def get_hash_string(input_string):
    # Create a new SHA-256 hash object
    sha256 = hashlib.sha256()
    # Update the hash object with the bytes of the input string
    sha256.update(input_string.encode('utf-8'))
    # Obtain the hexadecimal digest of the hash
    hash_hex = sha256.hexdigest()[:22]
    return hash_hex


def extract_test_output(s, pattern):
    s = s.split('\n')
    out = []
    append = False
    for one in s:
        if one.startswith('+') and pattern in one:
            append = True
        # the next command started here, so we finished reading test output
        elif append and one.startswith('+'):
            return '\n'.join(out)
        if append:
            out.append(one)
