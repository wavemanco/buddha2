---
dataset_info:
  config_name: full_agreement
  features:
  - name: ID
    dtype: string
  - name: Dataset
    dtype: string
  - name: Set
    dtype: string
  - name: DatasetsSplit
    dtype: string
  - name: Language
    dtype: string
  - name: Prompt
    dtype: string
  - name: RatingLabel
    dtype: string
  - name: Response
    dtype: string
  - name: TasksNamesFull
    dtype: string
  - name: TaskType
    dtype: string
  - name: facsco_grm_scaled
    dtype: float64
  - name: FullPrompt
    dtype: string
  splits:
  - name: train
    num_bytes: 10827210
    num_examples: 16948
  - name: val
    num_bytes: 1403770
    num_examples: 2180
  - name: test
    num_bytes: 1255708
    num_examples: 2004
  - name: heldout_item
    num_bytes: 924431
    num_examples: 1940
  - name: heldout_task
    num_bytes: 54887
    num_examples: 187
  download_size: 1334938
  dataset_size: 14466006
configs:
- config_name: full_agreement
  data_files:
  - split: train
    path: full_agreement/train-*
  - split: val
    path: full_agreement/val-*
  - split: test
    path: full_agreement/test-*
  - split: heldout_item
    path: full_agreement/heldout_item-*
  - split: heldout_task
    path: full_agreement/heldout_task-*
license: mit
language:
- en
---
# Multi-task Creativity Evaluation Dataset (MuCE)

This dataset is introduced in the [Creative Preference Optimization](https://arxiv.org/abs/2505.14442) and contains human responses and ratings for multiple creativity assessments.

### Dataset Sources

See [Creative Preference Optimization](https://arxiv.org/abs/2505.14442) for a list of sources.

## Citation
```
@misc{ismayilzada2025creativepreferenceoptimization,
      title={Creative Preference Optimization}, 
      author={Mete Ismayilzada and Antonio Laverghetta Jr. and Simone A. Luchini and Reet Patel and Antoine Bosselut and Lonneke van der Plas and Roger E. Beaty},
      year={2025},
      eprint={2505.14442},
      archivePrefix={arXiv},
      primaryClass={cs.CL},
      url={https://arxiv.org/abs/2505.14442}, 
}
```
