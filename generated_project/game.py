"""Game module containing core constants and utilities.

This module defines the scoring and attempt limits for the game, and provides a helper
function to load the list of valid words from the ``words.txt`` file located in the
project root.
"""

# Standard library imports
import random
import sys
from typing import List, Set
from dataclasses import dataclass, field

# Game constants
POINTS_PER_CORRECT: int = 10
MAX_ATTEMPTS: int = 2


def load_word_list(filepath: str) -> List[str]:
    """Load a list of words from a file.

    The function reads the file at ``filepath`` (expected to be ``words.txt``),
    strips any surrounding whitespace from each line, filters out empty lines,
    and returns the resulting list of words.

    Args:
        filepath: Path to the word list file.

    Returns:
        A list of non‑empty, stripped word strings.
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            # Read all lines, strip whitespace, and filter out empty strings
            words = [line.strip() for line in f.readlines() if line.strip()]
        return words
    except FileNotFoundError:
        # If the file cannot be found, output an error message and exit the program.
        sys.stderr.write(f"Error: Word list file not found at '{filepath}'.\n")
        sys.exit(1)
    except Exception as e:
        # Catch any other I/O errors, report them, and exit.
        sys.stderr.write(f"Error reading word list: {e}\n")
        sys.exit(1)


def jumble_word(word: str) -> str:
    """Return a scrambled version of *word*.

    The algorithm converts the input string into a list of characters and
    repeatedly shuffles it using :func:`random.shuffle` until the resulting
    arrangement differs from the original word. To avoid an infinite loop for
    short or repetitive words, the shuffle is attempted at most ten times; if
    no different ordering is produced, the original word is returned unchanged.

    Args:
        word: The word to be scrambled.

    Returns:
        A new string containing the shuffled characters, or the original word
        if a different permutation could not be generated within the retry
        limit.
    """
    if len(word) <= 1:
        # Single‑character words cannot be shuffled into a different order.
        return word

    original = list(word)
    shuffled = original[:]
    attempts = 0
    while attempts < 10:
        random.shuffle(shuffled)
        if shuffled != original:
            return "".join(shuffled)
        attempts += 1
    # Fallback: return the original word if no different permutation found.
    return word


@dataclass
class GameState:
    """Mutable game state shared across the application.

    Attributes:
        score: Current player score, starting at 0.
        word_list: List of possible words for the game.
        used_words: Set of words that have already been selected.
    """

    score: int = 0
    word_list: List[str] = field(default_factory=list)
    used_words: Set[str] = field(default_factory=set)

    def pick_new_word(self) -> str:
        """Select a random unused word from ``word_list``.

        The chosen word is added to ``used_words`` and returned. If all words
        have already been used, a ``RuntimeError`` is raised.
        """
        # Determine which words have not yet been used.
        available = [w for w in self.word_list if w not in self.used_words]
        if not available:
            raise RuntimeError("All words have been exhausted.")
        # Randomly select one of the remaining words.
        word = random.choice(available)
        self.used_words.add(word)
        return word
