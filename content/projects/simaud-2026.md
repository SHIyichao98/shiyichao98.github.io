---
title: Rule-Level Reasoning for Performance-Aware Floorplan Generation
year: ANNSIM 2026
type: Research / Shape Grammar + Building Performance
cover: assets/site_images/research/simaud-2026/full/hero.jpg
gallery_full: assets/site_images/research/simaud-2026/full/01.jpg | assets/site_images/research/simaud-2026/full/02.jpg | assets/site_images/research/simaud-2026/full/03.jpg | assets/site_images/research/simaud-2026/full/04.jpg | assets/site_images/research/simaud-2026/full/05.jpg | assets/site_images/research/simaud-2026/full/06.jpg | assets/site_images/research/simaud-2026/full/07.jpg | assets/site_images/research/simaud-2026/full/08.jpg | assets/site_images/research/simaud-2026/full/09.jpg | assets/site_images/research/simaud-2026/full/10.jpg
summary: Integrating shape grammars, daylight simulation, surrogate modeling, and explainable AI to support performance-aware rule selection in architectural design.
authors: Yichao Shi, Athanassios Economou, Patrick Kastner
---

## Overview

This research develops a rule-level reasoning workflow that connects shape grammar-based floorplan generation with daylight performance simulation. A one-bedroom apartment grammar generates alternative layouts, which are evaluated in ClimateStudio using daylight metrics including spatial daylight autonomy (sDA), annual sunlight exposure (ASE), illuminance, and related performance indicators. Each design is represented by a compact rule-sequence feature vector, linking explicit grammar decisions directly to quantitative simulation outcomes.

A surrogate model based on XGBoost is trained to approximate the aggregated daylight score, while SHAP and Partial Dependence Plots are used to identify which rule choices are most strongly associated with predicted performance. These signals support a rule-level reasoning engine that performs both global ranking of rule combinations and local searches for candidate single-rule edits, allowing full simulation to be reserved for a smaller set of promising alternatives.

## Focus

- Shape Grammar & Performance-Aware Design
- Building Performance Simulation
- Daylight Analysis with ClimateStudio
- Surrogate Modeling with XGBoost
- Explainable AI with SHAP & PDP
- Neural-Symbolic Rule-Level Reasoning

## Role

First author and lead researcher, responsible for the research framework, shape grammar development, daylight simulation workflow, dataset construction, surrogate modeling, explainable AI analysis, rule-level reasoning system, and preparation of the research publication.
