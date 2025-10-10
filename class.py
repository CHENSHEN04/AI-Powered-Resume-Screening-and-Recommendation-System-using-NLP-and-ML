    def preprocess_data(self):
        # Drop rows with missing values
        self.df.dropna(subset=['Resume', 'Category'], inplace=True)
        
        # Clean text data
        self.df['Resume'] = self.df['Resume'].apply(lambda x: re.sub(r'\s+', ' ', x).strip())
        
        # Encode labels
        self.df['Category'] = self.df['Category'].astype('category')
        self.df['Label'] = self.df['Category'].cat.codes
        
        print("Data preprocessing completed.")
        return self.df

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