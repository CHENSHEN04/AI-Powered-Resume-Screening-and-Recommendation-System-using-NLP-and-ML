import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.svm import LinearSVC
from sklearn.metrics import accuracy_score, classification_report
import matplotlib.pyplot as plt
import numpy as np
from sklearn.metrics import confusion_matrix, ConfusionMatrixDisplay
import joblib

# Load dataset
class MoodClassifierTrainer:
    def __init__(self, data_path="C:\CapStone\dataset.csv"):
        self.data_path = data_path
        # --- Select features (exclude valence and energy to prevent leakage) ---
        self.features = ['danceability','loudness','speechiness','acousticness',
                    'instrumentalness','liveness','tempo','mode','time_signature']
        self.df = pd.read_csv(self.data_path)
        print(f"Dataset shape: {self.df.shape[0]} rows, {self.df.shape[1]} columns")
        self.df['mood'] = self.df.apply(self.mood_category, axis=1)
        self.X = self.df[self.features]
        self.y = self.df['mood']
        self.scaler = StandardScaler()
        self.X_train, self.X_test, self.y_train, self.y_test = train_test_split(
            self.X, self.y, test_size=0.2, random_state=42, stratify=self.y)
        self.X_train = self.scaler.fit_transform(self.X_train)
        self.X_test = self.scaler.transform(self.X_test)

# --- Create mood categories based on valence & energy ---
    @staticmethod
    def mood_category(row):
        if row['valence'] >= 0.5 and row['energy'] >= 0.5:
            return 'Happy'
        elif row['valence'] >= 0.5 and row['energy'] < 0.5:
            return 'Calm'
        elif row['valence'] < 0.5 and row['energy'] < 0.5:
            return 'Sad'
        else:
            return 'Angry'

# Train and evaluate multiple models
    # Logistic Regression
    def train_logistic_regression(self):
        self.lr = LogisticRegression()
        self.lr.fit(self.X_train, self.y_train)
        joblib.dump(self.lr, 'logistic_regression_model.pkl')
        y_pred_lr = self.lr.predict(self.X_test)
        print("Logistic Regression Accuracy:", accuracy_score(self.y_test, y_pred_lr))
        print("Logistic Regression Report:\n", classification_report(self.y_test, y_pred_lr))
        return self.lr

    # Random Forest
    def train_random_forest(self):
        self.rf = RandomForestClassifier()
        self.rf.fit(self.X_train, self.y_train)
        joblib.dump(self.rf, 'random_forest_model.pkl')
        y_pred_rf = self.rf.predict(self.X_test)
        print("Random Forest Accuracy:", accuracy_score(self.y_test, y_pred_rf))
        print("Random Forest Report:\n", classification_report(self.y_test, y_pred_rf))
        return self.rf

    # Support Vector Machine
    def train_svm(self):
        self.svm = LinearSVC()
        self.svm.fit(self.X_train, self.y_train)
        joblib.dump(self.svm, 'svm_model.pkl')
        y_pred_svm = self.svm.predict(self.X_test)
        print("SVM Accuracy:", accuracy_score(self.y_test, y_pred_svm))
        print("SVM Report:\n", classification_report(self.y_test, y_pred_svm))
        return self.svm

    # Confusion Matrix for Random Forest
    def plot_confusion_matrix(self, rf):
        y_pred_rf = self.rf.predict(self.X_test)
        cm = confusion_matrix(self.y_test, y_pred_rf, labels=rf.classes_)
        disp = ConfusionMatrixDisplay(cm, display_labels=rf.classes_)
        disp.plot(xticks_rotation=45)

        importances = rf.feature_importances_
        indices = np.argsort(importances)[::-1]

        # Plot feature importances
        plt.figure(figsize=(10,5))
        plt.bar(range(len(self.features)), importances[indices])
        plt.xticks(range(len(self.features)), [self.features[i] for i in indices], rotation=45)
        plt.title("Feature Importance (Random Forest - 4-Class Mood Model)")
        plt.xlabel("Feature")
        plt.ylabel("Importance Score")
        plt.show()
    
    def train_and_save_models(self):
        lr_model = self.train_logistic_regression()
        rf_model = self.train_random_forest()
        svm_model = self.train_svm()
        self.plot_confusion_matrix(rf_model)

# Usage example:
if __name__ == "__main__":
    trainer = MoodClassifierTrainer("C:\CapStone\dataset.csv")
    trainer.train_and_save_models()