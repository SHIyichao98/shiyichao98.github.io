---
title: Benchmarking pix2pix on Floor Plans
year: CAADRIA 2026
type: Research / Shape Grammar + AI Benchmarking
cover: assets/site_images/research/caadria-2026/full/hero.jpg
gallery_full: assets/site_images/research/caadria-2026/full/01.jpg | assets/site_images/research/caadria-2026/full/02.jpg | assets/site_images/research/caadria-2026/full/03.jpg | assets/site_images/research/caadria-2026/full/04.jpg | assets/site_images/research/caadria-2026/full/05.jpg | assets/site_images/research/caadria-2026/full/06.jpg | assets/site_images/research/caadria-2026/full/07.jpg | assets/site_images/research/caadria-2026/full/08.jpg | assets/site_images/research/caadria-2026/full/09.jpg | assets/site_images/research/caadria-2026/full/10.jpg | assets/site_images/research/caadria-2026/full/11.jpg | assets/site_images/research/caadria-2026/full/12.jpg
summary: Using shape grammar as a deterministic benchmark to test the performance limits, functional validity, and data saturation of AI-based floor-plan generation.
authors: Yichao Shi, Tzu-Chieh Kurt Hong
links: [Paper](https://papers.cumincad.org/cgi-bin/works/paper/caadria2026_544)
---

## Overview

This research introduces a deterministic benchmarking framework for evaluating pix2pix in architectural floor-plan generation. A fixed shape grammar maps low-detail parti diagrams to furnished floor plans, creating rule-consistent paired datasets with controlled training, validation, and test splits. By holding the model architecture and optimization settings constant across multiple dataset sizes, the study isolates how training-data scale affects model performance.

The benchmark combines structural similarity index measure (SSIM) with an expert-reviewed Floor Plan Validity Index (FPVI), which evaluates both functional validity and drafting quality. Results show that test SSIM reaches a stable ceiling at around 1,000 training pairs, while additional data mainly improves convergence speed and drafting cleanliness rather than functional correctness. The gap between high SSIM and persistent plan errors demonstrates that visual similarity alone is insufficient for evaluating architectural generative models.

## Focus

- Shape Grammar as a Deterministic Benchmark
- pix2pix & Image-to-Image Generation
- Floor Plan Generation
- Dataset Scale & Performance Saturation
- SSIM & Floor Plan Validity Index
- Functional Validity of AI-Generated Designs

## Role

First author and lead researcher, responsible for the benchmarking framework, experimental design, pix2pix training and evaluation, performance analysis, FPVI development, interpretation of model limits, and preparation of the research publication.
