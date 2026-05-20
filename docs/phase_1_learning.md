# Phase 1 Learning Guide

Goal: understand the MVP well enough that you can explain how one prospect becomes one recommendation.

## Step 1: Understand The Data

Open these files first:

- `data/prospects.csv`
- `data/events.csv`

`prospects.csv` contains the people we may contact.

Example:

```csv
P001,Amina,Bennani,amina@example.com,Atlas Retail,Marketing Director,Retail,Sender,active,0
```

That row means:

- prospect id: `P001`
- name: `Amina Bennani`
- company: `Atlas Retail`
- status: `active`
- last contacted day: `0`

`events.csv` contains what prospects did after receiving emails.

Example:

```csv
P001,click,J0,0,10
```

That row means:

- prospect `P001`
- clicked an email
- campaign step `J0`
- day `0`
- hour `10`

## Step 2: Understand Python Objects

Open:

- `src/lnc_agent/models.py`

The project uses `dataclass` to describe data.

Simple idea:

```python
Prospect(...)
```

means "one prospect represented as a Python object."

This is easier than passing raw CSV rows everywhere.

## Step 3: Understand CSV Reading

Open:

- `src/lnc_agent/io.py`

Important functions:

- `read_prospects(...)`
- `read_events(...)`

These functions convert CSV rows into Python objects.

## Step 4: Run The Practice Script

Run:

```bash
python3 examples/phase_1_read_data.py
```

This prints the first prospect and the first event so you can see the transformation.

## Step 5: Understand The Whole Flow

Run the full agent:

```bash
python3 -m src.lnc_agent.cli run --prospects data/prospects.csv --events data/events.csv --out output
```

Then inspect:

```bash
cat output/recommendations.csv
```

## Step 6: Check Your Understanding

Answer these in your own words:

1. What is a `Prospect`?
2. What is an `Event`?
3. Why do we convert CSV rows into Python objects?
4. What file creates the recommendations?
5. What command runs the agent?

When you can answer those, Phase 1 part one is complete.
