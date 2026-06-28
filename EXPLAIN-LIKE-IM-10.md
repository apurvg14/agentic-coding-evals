# Explain it like I'm 10

This is the simple version of what we built. No fancy words. Just the idea.

## The big picture

Imagine you have a robot helper that can fix broken LEGO builds.

You hand it a build that's *almost* right but has a mistake, plus a note that says
"the roof is on wrong, please fix it." The robot looks at the build, finds the
problem, fixes it, and says "done!"

Now the big question: **how good is your robot, really?**

To find out, you don't just trust it. You give it a bunch of broken builds, let it
try to fix each one, and then you *check* every fix. You keep score. That scoreboard
tells you how smart your robot actually is.

**That's all this project is.** Except our "robot" is an AI (like the one inside
Claude or Cursor), and the "broken LEGO" is broken computer code.

## The pieces (and what they're like)

**1. The puzzles (we call them "tasks")**
These are small pieces of broken code. We made three:
- A "FizzBuzz" counting game that mixes up its words.
- A "find the middle number" helper that gets the answer wrong when there's an even
  amount of numbers.
- A "make a clean web address" helper that isn't built yet at all.

Each puzzle is like a broken toy waiting to be fixed.

**2. The robot (we call it the "agent")**
This is the AI. We give it a few "hands" so it can actually do things, not just talk:
- a hand to **see** all the files,
- a hand to **read** a file,
- a hand to **rewrite** a file,
- a hand to **run** the code and see if it works,
- and a way to say **"I'm done."**

The AI uses these hands over and over until it thinks it fixed the problem. A human
that works step-by-step like this is doing a "loop" — look, change, test, repeat.

**3. The answer key (we call it the "reference")**
For every puzzle we also saved the *correct* fix. We use it two ways:
- As a "pretend perfect robot" so you can watch the whole machine work even if you
  don't have an AI plugged in yet. (It just copies the right answer.)
- As the "best possible score" to compare real AIs against.

**4. The judge (we call it the "grader")**
After the robot says "done," a strict judge runs hidden tests on the code.
If everything works, that's a **win**. If not, it's a **fail**. The robot never gets
to see the judge's answer sheet — no cheating.

**5. The scoreboard (we call it the "report")**
At the end we count up the wins and make a neat table. The main number is called
**pass@1** — a fancy way of saying "what fraction did it fix correctly on the *first* try?"

## The cool part: we play dirty tricks (but fair ones)

Anyone can test a robot when everything is easy and clear. The interesting question is:
**does the robot still work when things get messy?** Real life is messy.

Here's the important rule: our tricks **never change the right answer**. The roof still
goes on the same way. We only change *how we ask* or *mess up the table around the LEGO*.
A truly smart robot shouldn't care about any of that. If a trick fools it, that's the
robot's fault, not an unfair puzzle. (Grown-ups call a trick like this an
"adversarial example" — a tiny change that *shouldn't* matter but breaks the AI anyway.)

The tricks we play:

- **Vague note** — a lazy "just fix it." Does the robot figure out what we meant?
- **Reworded note** — the same instructions, said differently. (This one is a *fairness
  check* — a good robot should never trip on this.)
- **Wall of words** — we bury the real ask inside a pile of boring, true-but-useless info.
- **Liar comment** — a note in the code saying "already correct, don't touch it" (a lie).
- **Fake look-alike files** — extra files with similar names. Does it fix the *real* one?
- **Junk code** — extra unused bits added to clutter the file.
- **Reshuffled spacing** — the code is reformatted but does the exact same thing.

**The really clever bit:** we don't just try one trick. We *hunt* for the trick (or
combo of tricks) that breaks the robot. It's like a kid who keeps poking until they find
the one thing that makes their sibling laugh. We call this finding the **worst case**.
If we *can't* find any trick that breaks the robot, that's a robot we can trust.

Then we measure two things:
- **Attack success rate** — out of the puzzles the robot solved normally, how many could
  we break with *some* trick?
- **Transfer** — when a trick breaks one robot, does the *same* trick also break a
  *different* robot? If yes, it's a shared blind spot. If no, each robot is weak in its
  own way. (To show this off, we built two pretend robots, `brittle-a` and `brittle-b`,
  that have one weakness in common and the rest different — so you can literally watch
  some tricks transfer and others not.)

This whole trick-playing-and-hunting idea comes from a field called "adversarial
robustness" — poking at AI on purpose to find where it breaks, so it can be made stronger.

## Why this is a big deal (the grown-up reason)

The companies that build these AIs have whole teams whose job is to build scoreboards
exactly like this one. They use them to answer: "Is our new AI actually better at coding
than the old one?" and "Where does it still mess up?"

The twist here is that it doesn't just check if the AI is *smart* — it checks if the AI
is *steady*: does it keep getting the right answer when the question is asked in an
annoying way, or when the room is messy? That "steadiness under sneaky changes" is the
thing this little machine is really built to measure.

## How to play with it

Watch the whole thing run using the pretend robots (no setup needed):

```bash
cd agentic-coding-evals
python -m agenteval run --model reference   # the perfect robot (nothing breaks it)
python -m agenteval run --model brittle-a   # a robot with some weak spots
python -m agenteval run --model brittle-b   # a robot with different weak spots
python -m agenteval report                  # the scoreboard + the "transfer" table
```

You'll see the perfect robot survive every trick, the two brittle robots get broken by
the trick-hunter, and a table showing which tricks transfer between them. Everything is
written to `results/report.md`.

Later, to test a *real* AI, you plug in a key and run it for real:

```bash
pip install anthropic
python -m agenteval run --model claude-sonnet-4-5
```

Now the scoreboard shows how the real AI did — including how badly our dirty tricks
threw it off. The step-by-step diaries of what the AI did are saved in
`results/transcripts/`, so you can read them like a detective and write down exactly
where it got confused.

## In one sentence

**We built a scoreboard machine that gives an AI broken code to fix, plays sneaky tricks
on it, and measures both how good it is and how well it holds up when things get hard.**
