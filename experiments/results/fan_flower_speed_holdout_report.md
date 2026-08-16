# Fan flower speed-generalization experiment

Source: `nimaabaeian/ml-project-robotic-fan-fault-detection/accelerometer.csv`

Dataset: 153,000 rows; weight configurations 1, 2, 3; fan speeds 20% through 100% in 5% steps. Every configuration/speed block contains 3,000 samples.

Method: 16,983 non-overlapping nine-sample windows. No window crosses a configuration or speed boundary. The flower mapping is the frozen earlier mapping: train-only axis standardization; nine softmax petal weights; fixed angular perturbation; five geometric measures per axis (area, perimeter, centroid asymmetry, radial roughness, anisotropy), for 15 total features. All representations use the same StandardScaler + multinomial logistic-regression pipeline.

Speed split: train 20–60%; validation 65–75%; untouched high-speed test 80–100%. Chance for the three equally represented configurations is 0.3333.

## Results

| representation | validation balanced accuracy | test balanced accuracy | test macro F1 | random-split balanced accuracy |
|---|---:|---:|---:|---:|
| Flower geometry (15) | 0.6770 | 0.3848 | 0.2821 | 0.5806 |
| RMS (3) | 0.5903 | 0.3890 | 0.3101 | 0.5737 |
| Ordinary summaries (15) | 0.5602 | 0.2997 | 0.2754 | 0.5967 |
| Raw sequence (27) | 0.3907 | 0.3516 | 0.3276 | 0.4120 |
| Shape-only normalized raw (27) | 0.3307 | 0.3251 | 0.3245 | 0.3329 |

The flower representation is clearly strongest on the moderate unseen-speed validation range (65–75%), but it does not remain invariant across the larger jump to 80–100%. At the high-speed test it is essentially tied with RMS on balanced accuracy and has lower macro F1 than raw sequence because its predictions collapse mainly toward configuration 1.

## High-speed test confusion matrices

Rows are true configuration 1, 2, 3; columns are predicted configuration 1, 2, 3.

Flower geometry:
```
[[1620,   45,    0],
 [1627,   38,    0],
 [1147,  254,  264]]
```

RMS:
```
[[1648,   17,    0],
 [1583,   82,    0],
 [ 178, 1274,  213]]
```

Raw sequence:
```
[[718, 785, 162],
 [686, 832, 147],
 [544, 915, 206]]
```

Shape-only raw:
```
[[527, 578, 560],
 [513, 613, 539],
 [572, 609, 484]]
```

Ordinary summaries:
```
[[1004,  115,  546],
 [ 954,  278,  433],
 [ 433, 1017,  215]]
```

## Diagnostic implication

The important failure is configuration 1 versus configuration 2 at high speed. The next diagnostic should map each configuration's flower-feature centroid as a function of speed. If the configuration-1 and configuration-2 trajectories converge or cross near 80%, that directly explains the collapse and tells us which geometric quantity must be changed rather than blindly tuning the classifier.
