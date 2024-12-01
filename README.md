# Multimodal Semantic Decoupling Prompting for Zero-Shot Referring Expression Comprehension

Official Codes for Multimodal Semantic Decoupling Prompting for Zero-Shot Referring Expression Comprehension.

![Farmework of MSDP.](./assist/Framework_MSDP.png)

Framework of Multimodal Semantic Decoupling Prompting.

## Requirement

* Pip packages:

  > pip install -r requirements.txt
  >

## Usage

### Dataset Preparation

Our code is built upon [FGVP](https://arxiv.org/abs/2306.04356). The installation instructions and the preparation of datasets are the same as the [FGVP repository](https://github.com/ylingfeng/FGVP?tab=readme-ov-file).

This repository needs RefCOCO, RefCOCO+, and RefCOCOg. All datasets are supposed to be under ./data.

Run Code

```python
python cmds/MSDP.py
```
