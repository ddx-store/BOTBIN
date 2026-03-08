def luhn_checksum(card_number):
    def digits_of(n):
        return [int(d) for d in str(n)]

    digits = digits_of(card_number)
    odd_digits = digits[-1::-2]
    even_digits = digits[-2::-2]
    checksum = sum(odd_digits)
    for d in even_digits:
        checksum += sum(digits_of(d * 2))
    return checksum % 10


def calculate_luhn(partial_card_number):
    return (10 - luhn_checksum(partial_card_number * 10)) % 10


def is_valid_luhn(card_number):
    return luhn_checksum(int(card_number)) == 0
