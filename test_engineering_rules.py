# 测试工程铁律功能的示例代码

# 铁律 2 测试: 废弃 API
from botorch.models.gp_regression import FixedNoiseGP
from sklearn.cross_validation import train_test_split  # 废弃 API

# 铁律 1 测试: ML 框架
import torch
import gpytorch
import tensorflow
import xgboost
import lightgbm

# 普通包
import numpy
import pandas
