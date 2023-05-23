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
    def __int__(self, padding_name, learner_params, fit_params, hash_value, cv_iterations, n_hypothesis, base_directory,
                validation_loss, random_state=None, **kwargs):
        super().__int__(padding_name=padding_name, learner_params=learner_params, fit_params=fit_params,
                        hash_value=hash_value, cv_iterations=cv_iterations, n_hypothesis=n_hypothesis,
                        base_directory=base_directory, random_state=random_state, **kwargs)
        self.base_detector = AutoGluonClassifier
        self.learner_params['output_folder'] = os.path.join(base_directory, OPTIMIZER_FOLDER, f"{hash_value}gluon")
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
                self.logger.info(f"************************************ Split {k} ************************************")
                train_index = train_index[:train_size]
                X_train, X_test = X[train_index], X[test_index]
                y_train, y_test = y[train_index], y[test_index]
                self.calculate_majority_voting_accuracy(X_train, y_train, X_test, y_test)

                train_data = self.base_detector.convert_to_dataframe(X_train, y_train)
                test_data = self.base_detector.convert_to_dataframe(X_test, None)
                X_t = train_data.drop(columns=['class'])  # Extract the features from the training data
                y_t = train_data['class']  # Extract the labels from the training data
                for i, model in enumerate(self.estimators):
                    self.logger.info(f"************************************ Model {i} ************************************")
                    model._n_repeats_finished = 0
                    n_repeat_start = 0
                    model.fit(X=X_t, y=y_t, n_repeat_start=n_repeat_start)
                    p_pred, y_pred = get_scores(test_data, model)
                    for metric_name, evaluation_metric in mi_estimation_metrics.items():
                        if LOG_LOSS_MI_ESTIMATION in metric_name or PC_SOFTMAX_MI_ESTIMATION in metric_name:
                            calibrator_technique = None
                            for key in calibrators.keys():
                                if key in metric_name:
                                    calibrator_technique = key
                            if calibrator_technique is not None:
                                calibrator = calibrators[calibrator_technique]
                                c_params = calibrator_params[calibrator_technique]
                                calibrator = calibrator(**c_params)
                                try:
                                    p_pred_cal = probability_calibration(X_train, y_train, X_test, model, calibrator,
                                                                         self.logger)
                                    metric_loss = evaluation_metric(y_test, p_pred_cal)
                                except Exception as error:
                                    log_exception_error(self.logger, error)
                                    self.logger.error("Error while calibrating the probabilities")
                                    metric_loss = evaluation_metric(y_test, p_pred)
                            else:
                                metric_loss = evaluation_metric(y_test, p_pred)
                        else:
                            metric_loss = evaluation_metric(y_test, y_pred)
                        self.logger.info(f"Metric {metric_name}: Value {metric_loss}")
                        model_name = list(self.results.keys())[i]
                        self.results[model_name][metric_name].append(metric_loss)
            self.store_results()
