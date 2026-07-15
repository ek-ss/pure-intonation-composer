# Development Plan

**Project:** Pure Intonation Composer

Version: 0.1

---

# 1. Purpose

This document defines the implementation roadmap for the project.

Development proceeds incrementally.

Every phase must produce a fully working system.

No unfinished features should block subsequent phases.

---

# 2. Development Principles

1. Build small working systems.
2. Every feature must have automated tests.
3. Public APIs require documentation.
4. New features must not break existing projects.
5. All algorithms must be deterministic when using the same random seed.

---

# 3. Milestones

| Phase | Goal                  |
| ----- | --------------------- |
| P1    | Mathematical Core     |
| P2    | Harmonic Graph        |
| P3    | Composition Engine    |
| P4    | Rhythm Engine         |
| P5    | Audio Rendering       |
| P6    | Export                |
| P7    | REST API              |
| P8    | Web UI                |
| P9    | Real-time Performance |
| P10   | Stable Release        |

---

# Phase 1 – Mathematical Core

## Issue 1

Ratio class

Tasks

* implement Fraction wrapper
* normalization
* octave reduction
* cent conversion

Acceptance Criteria

* ratios normalize into one octave
* unit tests pass

---

## Issue 2

Monzo

Tasks

* prime decomposition
* vector conversion

Acceptance Criteria

* known ratios produce expected monzos

---

## Issue 3

CPS Generator

Tasks

* CPS(n,k)
* Harmonic
* Subharmonic

Acceptance Criteria

* CPS(6,3) generates 20 unique pitch classes
* octave normalization works

---

## Issue 4

Euler–Fokker Generator

Tasks

* arbitrary prime limits
* exponent ranges

Acceptance Criteria

* generated ratios match analytical expectations

---

# Phase 2 – Harmonic Graph

## Issue 5

Johnson Graph

Tasks

* node generation
* edge generation

Acceptance Criteria

* graph size matches combinatorial formula
* connected graph

---

## Issue 6

Graph Algorithms

Tasks

* shortest path
* weighted walk
* random walk

Acceptance Criteria

* deterministic with fixed seed

---

## Issue 7

Distance Metrics

Tasks

* harmonic distance
* monzo distance
* cent distance

Acceptance Criteria

* symmetric
* zero on identical nodes

---

# Phase 3 – Composition Engine

## Issue 8

Harmony Generator

Tasks

* graph traversal
* transition scoring

Acceptance Criteria

* progression length configurable
* no disconnected transitions

---

## Issue 9

Voice Leading

Tasks

* common tone optimization
* leap minimization

Acceptance Criteria

* no voice crossing
* configurable leap limits

---

## Issue 10

Bass Generator

Tasks

* mirror ratios
* continuity scoring
* register optimization

Acceptance Criteria

* generated bass supports every chord
* no impossible octave jumps

---

## Issue 11

Melody Generator

Tasks

* independent voices
* phrase memory
* contour control

Acceptance Criteria

* melody remains inside configured register

---

# Phase 4 – Rhythm

## Issue 12

Euclidean Rhythm

Acceptance Criteria

* exact pulse distribution

---

## Issue 13

State Transition Graph

Acceptance Criteria

* Hamming distance one

---

## Issue 14

Phase Shift

Acceptance Criteria

* independent cycle lengths

---

## Issue 15

Humanization

Acceptance Criteria

* configurable timing
* deterministic seed

---

# Phase 5 – Audio

## Issue 16

Oscillators

* sine
* saw
* square
* triangle
* additive

---

## Issue 17

Envelope

ADSR

---

## Issue 18

Effects

Delay

Reverb

Limiter

---

## Issue 19

Offline Rendering

Acceptance Criteria

* WAV export succeeds

---

# Phase 6 – Export

## Issue 20

MIDI

---

## Issue 21

Scala

---

## Issue 22

JSON

---

# Phase 7 – REST API

## Issue 23

FastAPI

Acceptance Criteria

* OpenAPI generated
* Swagger works

---

## Issue 24

Async Rendering

Acceptance Criteria

* job queue functional

---

# Phase 8 – Web UI

## Issue 25

Keyboard

---

## Issue 26

Graph Viewer

---

## Issue 27

Circle View

---

## Issue 28

Timeline

---

## Issue 29

Recorder

---

# Phase 9 – Real-Time Performance

## Issue 30

WebSocket

---

## Issue 31

Transport

---

## Issue 32

Live Improvisation

---

# Phase 10 – Stable Release

Tasks

Performance optimization

Documentation

Examples

Packaging

Installer

---

# Testing Strategy

Every module contains

Unit tests

Integration tests

Regression tests

Property tests where applicable

Coverage target

90%

---

# Performance Targets

Graph generation

< 1 second

Random walk

10000 transitions per second

Offline rendering

10× real time

Memory

< 1 GB

---

# Code Style

Python 3.12

PEP8

Type hints mandatory

black

ruff

mypy

pytest

---

# Branch Strategy

main

Stable releases

develop

Integration

feature/*

Individual issues

---

# Pull Request Rules

Every PR requires

Passing tests

Documentation updates

Type checking

Code review

---

# Definition of Done

A task is complete only if

* implementation finished
* tests added
* documentation updated
* API documented
* examples included
* lint passes
* type checks pass
* reproducible using fixed random seed

---

# Future Versions

Version 0.2

MPE

OSC

SuperCollider

VCV Rack

Version 0.3

GPU synthesis

Distributed rendering

AI-assisted composition

Adaptive harmonic models
