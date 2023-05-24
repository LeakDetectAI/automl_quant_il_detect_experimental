import logging
import os.path

from .ild_base_class import InformationLeakageDetector
from .utils import mi_estimation_metrics, calibrators, calibrator_params
from .. import AutoGluonClassifier
from ..bayes_search_utils import get_scores
from ..contants import *
from ..metrics import probability_calibration
from ..utils import log_exception_error


class AutoGluonLeakageDetector(InformationLeakageDetector):
    def __init__(self, padding_name, learner_params, fit_params, hash_value, cv_iterations, n_hypothesis,
                 base_directory, validation_loss, random_state=None, **kwargs):
        super().__init__(padding_name=padding_name, learner_params=learner_params, fit_params=fit_params,
                         hash_value=hash_value, cv_iterations=cv_iterations, n_hypothesis=n_hypothesis,
                         base_directory=base_directory, random_state=random_state, **kwargs)
        self.base_detector = AutoGluonClassifier
        folder_name = f"{hash_value}_{self.padding_name}gluon"
        self.learner_params['output_folder'] = os.path.join(base_directory, OPTIMIZER_FOLDER, folder_name)
        self.learner_params['eval_metric'] = validation_loss
        self.learner_params['delete_tmp_folder_after_terminate'] = False
        self.base_detector = AutoGluonClassifier(**self.learner_params)
        self.logger = logging.getLogger(AutoGluonLeakageDetector.__name__)

    def perform_hyperparameter_optimization(self, X, y):
        X_train, y_train = self.get_training_dataset(X, y)
        self.base_detector.fit(X_train, y_train)
        for i in range(self.n_hypothesis):
            model = self.base_detector.get_k_rank_model(i + 1)
            self.estimators.append(model)
        train_size = X_train.shape[0]
        return train_size

    def fit(self, X, y, **kwargs):
        if self._is_fitted_:
            self.logger.info(f"Model already fitted for the padding {self.padding_name}")
        else:
            train_size = self.perform_hyperparameter_optimization(X, y)
            for k, (train_index, test_index) in enumerate(self.cv_iterator.split(X, y)):
                self.logger.info(f"********************************* Split {k+1} *********************************")
                train_index = train_index[:train_size]
                X_train, X_test = X[train_index], X[test_index]
                y_train, y_test = y[train_index], y[test_index]
                self.calculate_majority_voting_accuracy(X_train, y_train, X_test, y_test)

                train_data = self.base_detector.convert_to_dataframe(X_train, y_train)
                test_data = self.base_detector.convert_to_dataframe(X_test, None)
                X_t = train_data.drop(columns=['class'])  # Extract the features from the training data
                y_t = train_data['class']  # Extract the labels from the training data
                for i, model in enumerate(self.estimators):
                    self.logger.info(f"************* Model {i}: {model.__class__.__name__} ********************")
                    model._n_repeats_finished = 0
                    n_repeat_start = 0
                    model.fit(X=X_t, y=y_t, n_repeat_start=n_repeat_start)
                    p_pred, y_pred = get_scores(test_data, model)
                    self.evaluate_scores(X_test, X_train, y_test, y_train, y_pred, p_pred, model, i)
            self.store_results()
