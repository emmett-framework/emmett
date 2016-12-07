from random import SystemRandom
import string


def get_cryptogen_string(str_length=32):
    chars = string.ascii_letters + string.digits + '!@#$%^&*()'
    cryptogen = SystemRandom()
    return ''.join(cryptogen.choice(chars) for _ in range(str_length))
