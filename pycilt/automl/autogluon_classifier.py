import logging
import os.path
import shutil

import numpy as np
import pandas as pd
from autogluon.tabular import TabularPredictor
from sklearn.utils import check_random_state

from pycilt.automl.automl_core import AutomlClassifier
from pycilt.automl.model_configurations import hyperparameters
from pycilt.utils import log_exception_error


class AutoGluonClassifier(AutomlClassifier):

    def __init__(self, n_features, n_classes, time_limit=1800, output_folder=None, eval_metric='accuracy',
                 use_hyperparameters=True, delete_tmp_folder_after_terminate=True, auto_stack=False,
                 random_state=None, **kwargs):
        self.logger = logging.getLogger(name=AutoGluonClassifier.__name__)
        self.random_state = check_random_state(random_state)
        self.output_folder = output_folder
        self.delete_tmp_folder_after_terminate = delete_tmp_folder_after_terminate
        self.hyperparameter_tune_kwargs = {'scheduler': 'local', 'searcher': 'auto'}
        self.eval_metric = eval_metric
        self.use_hyperparameters = use_hyperparameters
        if self.use_hyperparameters:
            self.hyperparameters = hyperparameters
        else:
            self.hyperparameters = None
        self.auto_stack = auto_stack
        self.n_features = n_features
        self.n_classes = n_classes
        self.sample_weight = "auto_weight"
        self.time_limit = time_limit
        self.model = None
        self.class_label = 'class'
        self.columns = [f'feature_{i}' for i in range(self.n_features)] + [self.class_label]
        if self.n_classes > 2:
            self.problem_type = 'multiclass'
        if self.n_classes == 2:
            self.problem_type = 'binary'
        self.leaderboard = None
        self.time_limit_reached = None
        #        if "pc2" in os.environ["HOME"]:
        #            tmp_dir_path = os.path.join(os.environ["PFS_FOLDER"], "tmp")
        #            if not os.path.isdir(tmp_dir_path):
        #                os.mkdir(tmp_dir_path)
        #            os.environ['RAY_LOG_DIR'] = os.environ['RAY_HOME'] = os.environ['TMPDIR'] = tmp_dir_path

    def check_if_fitted(self):
        if os.path.exists(self.output_folder):
            try:
                self.model = TabularPredictor.load(self.output_folder)
                self.logger.info(f"Loading the model at {self.output_folder}")
            except Exception as error:
                log_exception_error(self.logger, error)
                self.logger.error(f"Cannot load the trained model at {self.output_folder}")
                self.model = None
                try:
                    shutil.rmtree(self.output_folder)
                    self.logger.error(f"The folder '{self.output_folder}' and its contents are deleted successfully.")
                except OSError as error:
                    log_exception_error(self.logger, error)
                    self.logger.error(f"Error: {error.strerror}")

        if self.model is not None:
            self.leaderboard = self.model.leaderboard(extra_info=True)
            time_taken = self.leaderboard['fit_time'].sum() + self.leaderboard['pred_time_val'].sum()
            difference = self.time_limit - time_taken
            self.logger.info(f"Fitting time of the model {time_taken} and remaining {difference}")
            if difference >= 100:
                self.model = None

    def fit_timed(self, X, y, **kwd):
        self.logger.info("Timed Fitting")
        train_data = self.convert_to_dataframe(X, y)
        self.check_if_fitted()
        self.time_limit_reached = False
        if self.model is None:
            try:
                self.model = TabularPredictor(label=self.class_label, sample_weight=self.sample_weight,
                                              problem_type=self.problem_type, eval_metric=self.eval_metric,
                                              path=self.output_folder)
                self.model.fit(train_data, time_limit=self.time_limit, hyperparameters=hyperparameters,
                               hyperparameter_tune_kwargs=self.hyperparameter_tune_kwargs, auto_stack=self.auto_stack)
            except Exception as error:
                log_exception_error(self.logger, error)
                self.logger.error("Fit function execution timed out so loading the already trained model")

    def fit(self, X, y, **kwd):
        # Set the alarm to trigger after the specified time limit
        self.logger.info("Fitting Started")
        self.fit_timed(X, y, **kwd)
        self.leaderboard = self.model.leaderboard(extra_info=True)
        if self.delete_tmp_folder_after_terminate:
            self.model.delete_models(models_to_keep='best', dry_run=False)
            self.model.save_space()

    def predict(self, X, verbose=0):
        test_data = self.convert_to_dataframe(X, None)
        y_pred = self.model.predict(test_data)
        return y_pred.values

    def score(self, X, y, sample_weight=None, verbose=0):
        test_data = self.convert_to_dataframe(X, y)
        score = self.model.evaluate(test_data)['balanced_accuracy']
        return score

    def predict_proba(self, X, verbose=0):
        test_data = self.convert_to_dataframe(X, None)
        y_pred = self.model.predict_proba(test_data)
        return y_pred.values

    def decision_function(self, X, verbose=0):
        test_data = self.convert_to_dataframe(X, None)
        y_pred = self.model.predict_proba(test_data)
        return y_pred.values

    def convert_to_dataframe(self, X, y):
        if y is None:
            n_instances = X.shape[0]
            y = self.random_state.choice(self.n_classes, size=n_instances)
        data = np.concatenate((X, y[:, None]), axis=1)
        if self.n_features != X.shape[-1]:
            raise ValueError(f"Dataset passed does not contain {self.n_features}")
        df_data = pd.DataFrame(data=data, columns=self.columns)
        return df_data

    def get_k_rank_model(self, k):
        self.leaderboard.sort_values(['score_val'], ascending=False, inplace=True)
        model_name = self.leaderboard.iloc[k - 1]['model']
        model = self.model._trainer.load_model(model_name)
        return model

    def get_model(self, model_name):
        self.leaderboard.sort_values(['score_val'], ascending=False, inplace=True)
        # model_name = self.leaderboard.iloc[k - 1]['model']
        model = self.model._trainer.load_model(model_name)
        return model