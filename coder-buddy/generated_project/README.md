# Jumble Word Game

## Project Overview

The **Jumble Word Game** is a simple command‑line Python game that challenges players to unscramble a jumbled word. The player is presented with a mixed‑up version of a word and must type the correct original word. The game tracks the player's score and ends after two failed attempts on a single word.

## Prerequisites

- Python **3.8** or higher
- No external libraries are required (the game uses only the Python standard library)

## How to Run the Game

```bash
python game.py
```

Running the command above will start the game in your terminal.

## Controls

- **Enter** – Press **Enter** at the start screen to begin the first round.
- **Type a guess** – After a jumbled word is shown, type your guess and press **Enter**.
- **quit** – Type `quit` (case‑insensitive) at any time to exit the game immediately.

## Scoring Rules

- Each correct guess awards **+10 points**.
- The current total score is displayed after each round.
- The final score is shown when the game ends (either by quitting or after two consecutive failed attempts on a word).

## Game End Conditions

- The game ends automatically after **two failed attempts** on the same word.
- The player can also end the game early by typing `quit`.

## Example Session

```
$ python game.py

Welcome to the Jumble Word Game!
Press Enter to start...

[Press Enter]

Jumbled word: **ppla**
Your guess: apple
Correct! +10 points.
Score: 10

Jumbled word: **gnaro**
Your guess: orange
Correct! +10 points.
Score: 20

Jumbled word: **etbrru**
Your guess: turtle
Incorrect. Try again.
Your guess: butter
Correct! +10 points.
Score: 30

Jumbled word: **zxy**
Your guess: xyz
Incorrect.
Your guess: quit

Game over! Your final score: 30
```

Enjoy playing and try to beat your high score!
