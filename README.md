# Qualitative Analysis of Robotic Signal Components using Inductive Logic Programming

## Overview

This repository contains the implementation, datasets, and research material for the project:

**"Qualitative Analysis of Robotic Signal Components using Inductive Logic Programming (ILP)"**

The project investigates how raw numerical signals from robotic systems (sensors and actuators) can be transformed into qualitative, symbolic representations and used to learn interpretable models using ILP.

---

## Motivation

Modern robotic systems generate large volumes of numerical data from sensors and actuators. While data-driven approaches (e.g., deep learning) can model such data effectively, they often lack interpretability.

Inductive Logic Programming (ILP) provides a symbolic and explainable alternative by learning human-readable rules from:
- Background knowledge
- Positive examples
- Negative examples

This project aims to bridge the gap between **low-level numeric signals** and **high-level symbolic reasoning** in robotics.

---

## Objectives

The main objectives of this project are:

- Convert robotic time-series signals into qualitative representations
- Extract meaningful signal characteristics (e.g., increasing, decreasing, constant)
- Represent processed signals as logical facts
- Use ILP to induce interpretable rules for robot actions
- Analyze differences in signal patterns across robotic platforms

---

## Project Scope

This repository is structured to support experiments across different robotic platforms:

### Platforms Covered
- **Manipulator Robot (xArm)**
  - Pick-and-place tasks
  - Joint states (position, velocity, effort)

- **Mobile Robot**
  - Navigation behaviors (forward, backward, turning, wall-following)
  - Sensor-actuator interactions

---

## Branches

This repository is organized into multiple branches:

- **main**  
  Contains:
  - Project documentation
  - Literature review
  - Methodology
  - Shared code and utilities

- **xarm**  
  Contains:
  - Manipulator-specific experiments
  - Joint signal processing
  - ILP models for pick-and-place tasks

- **mobile**  
  Contains:
  - Mobile robot datasets
  - Navigation behavior analysis
  - ILP models for motion and sensor interaction

---

## Methodology

The project follows a structured pipeline:

1. **Data Collection**
   - Record robot actions (ROS bags / logs)

2. **Preprocessing**
   - Clean and segment signals into action windows

3. **Feature Extraction**
   - Identify qualitative characteristics:
     - Increasing / decreasing trends
     - Constant signals
     - Oscillations
     - Peaks / transitions

4. **Logical Representation**
   - Convert processed signals into logic facts

5. **ILP Learning**
   - Provide:
     - Background knowledge
     - Positive examples
     - Negative examples
   - Learn symbolic hypotheses

6. **Evaluation**
   - Analyze interpretability and correctness of learned rules

---

## Example Use Case

Example qualitative rule for a mobile robot action:

```prolog
move_forward :-
    increasing(velocity_left),
    increasing(velocity_right),
    constant(gyro_z).
```

This represents a human-readable explanation of the robot's behavior.

---

## Technologies Used

- Python (NumPy, Pandas, Matplotlib)
- ROS 2 (for data collection)
- Inductive Logic Programming tools (e.g., Aleph, Progol, Popper)
- Signal processing techniques (FFT, segmentation, smoothing)

---

## Research Context

This work is part of a broader research direction focusing on:

- Explainable Artificial Intelligence (XAI) in robotics
- Symbolic learning for robot behavior understanding
- Integration of data-driven and logic-based methods
- Potential applications in fault detection and diagnosis

---

## Setup

```bash
git clone https://github.com/<your-username>/qualitative-analysis-robotic-signal-components-ilp.git
cd qualitative-analysis-robotic-signal-components-ilp
pip install -r requirements.txt
```

---

## Future Work

- Integration with fault detection and diagnosis systems
- Hybrid models combining ILP and statistical methods
- Real-time symbolic reasoning
- Multi-robot system extensions

---

## License

This project is licensed under the MIT License.

---

## Authors

- Alisha Syed Karimulla
- Trushar Ghanekar

**MSc Autonomous Systems**  
Hochschule Bonn-Rhein-Sieg (H-BRS)