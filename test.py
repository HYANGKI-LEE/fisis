import os
import time
import pandas as pd
from argparse import Namespace, ArgumentParser

import fisis_getter
from config import base_cols, col_name_matching_dict, lrgDiv_dict, smlDiv_dict, display_cols
from util import make_dir


# A 국내은행 / H 생명보험 / I 손해보험 / F 증권사 / K 리스사 / M 부동산신탁
# # (start, end) = ('200703', '201612')
# # (start, end) = ('201703', '202403')
