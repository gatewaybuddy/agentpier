"""Registration challenge generation — multi-step math problems."""

import random
import secrets
import uuid

# First 25 primes for challenge generation
_PRIMES = [
    2,
    3,
    5,
    7,
    11,
    13,
    17,
    19,
    23,
    29,
    31,
    37,
    41,
    43,
    47,
    53,
    59,
    61,
    67,
    71,
    73,
    79,
    83,
    89,
    97,
]

# Words with known vowel counts for challenge generation
_WORDS = [
    ("authentication", 7),
    ("marketplace", 5),
    ("verification", 5),
    ("intelligence", 5),
    ("registration", 4),
    ("communication", 6),
    ("infrastructure", 5),
    ("documentation", 6),
    ("administrator", 5),
    ("collaboration", 6),
    ("extraordinary", 6),
    ("determination", 5),
    ("understanding", 4),
    ("international", 6),
    ("environmental", 5),
    ("approximately", 5),
    ("pronunciation", 6),
    ("revolutionary", 6),
]


def _type_primes_times_vowels():
    """Sum of first N primes multiplied by vowel count of a word."""
    n = random.randint(5, 10)
    word, vowel_count = random.choice(_WORDS)
    prime_sum = sum(_PRIMES[:n])
    answer = prime_sum * vowel_count
    text = (
        f"What is the sum of the first {n} prime numbers, "
        f"multiplied by the number of vowels in '{word}'?"
    )
    return text, answer


def _type_letter_sum_minus_constant():
    """Sum of letter values (A=1..Z=26) in a short word, combined with arithmetic."""
    words_and_sums = [
        ("AGENT", 47),
        ("TRUST", 93),
        ("PRIME", 61),
        ("CLOUD", 54),
        ("NORTH", 73),
        ("SOUTH", 83),
        ("PIXEL", 73),
        ("BYTES", 80),
        ("QUERY", 81),
        ("STACK", 55),
        ("TRADE", 47),
        ("BLOCK", 47),
        ("LOGIC", 47),
        ("NEXUS", 73),
        ("ORBIT", 66),
        ("SIGMA", 51),
    ]
    word, letter_sum = random.choice(words_and_sums)
    multiplier = random.randint(2, 5)
    offset = random.randint(10, 99)
    answer = letter_sum * multiplier - offset
    text = (
        f"If A=1, B=2, ..., Z=26, what is the sum of the letters in "
        f"'{word}' multiplied by {multiplier}, minus {offset}?"
    )
    return text, answer


def _type_arithmetic_chain():
    """Multi-step arithmetic: (a * b) + (c * d) - e."""
    a = random.randint(7, 25)
    b = random.randint(3, 12)
    c = random.randint(4, 15)
    d = random.randint(2, 9)
    e = random.randint(10, 50)
    answer = (a * b) + (c * d) - e
    text = f"Calculate: ({a} × {b}) + ({c} × {d}) - {e}"
    return text, answer


def _type_fibonacci_plus_prime():
    """Sum of first N Fibonacci numbers plus the Mth prime."""
    n = random.randint(6, 12)
    m = random.randint(5, 15)
    # Compute first n Fibonacci numbers (1-indexed: 1,1,2,3,5,8,...)
    fibs = [1, 1]
    for _ in range(n - 2):
        fibs.append(fibs[-1] + fibs[-2])
    fib_sum = sum(fibs)
    prime = _PRIMES[m - 1]  # m-th prime (1-indexed)
    answer = fib_sum + prime
    text = (
        f"What is the sum of the first {n} Fibonacci numbers "
        f"(starting 1, 1, 2, 3, ...) plus the {m}th prime number?"
    )
    return text, answer


_GENERATORS = [
    _type_primes_times_vowels,
    _type_letter_sum_minus_constant,
    _type_arithmetic_chain,
    _type_fibonacci_plus_prime,
]


def generate_challenge() -> dict:
    """Generate a registration challenge.

    Returns:
        {
            "challenge_id": str (UUID),
            "challenge_text": str (human-readable question),
            "expected_answer": int,
        }
    """
    generator = secrets.choice(_GENERATORS)
    text, answer = generator()

    return {
        "challenge_id": uuid.uuid4().hex[:12],
        "challenge_text": text,
        "expected_answer": int(answer),
    }
