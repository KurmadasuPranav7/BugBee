# """CLI entry point for the BugBee package.

# The original monolithic implementation lived in ``cli-wrapper/src/cli_wrapper/main.py``.
# This version keeps the ``run`` command as a clean pipeline built on top of:

# * ``bugbee.parser.error_parser`` – stack‑trace extraction, sanitisation, hashing
# * ``bugbee.cache`` – JSON cache wrapper
# * ``bugbee.retrieval`` – ChromaDB document retrieval
# * ``bugbee.llm`` – LLM provider abstraction
# * ``bugbee.patcher`` – safe patch application with backup
# * ``bugbee.validator`` – post‑patch validation runner
# * ``bugbee.metrics`` – metrics collection and JSONL persistence
# * ``bugbee.ui`` – ALL logging and terminal presentation (spinners, colored
#   status lines, panels, tables, confirmation prompts) lives here. This file
#   contains no direct ``log.*`` or ``typer.echo`` calls — every user-facing
#   message is routed through the ``ui`` singleton so the pipeline below reads
#   as pure business logic.

# The command line mimics the historic behaviour while being fully testable,
# type‑safe, and pleasant to actually use.
# """

# from __future__ import annotations

# import re
# import sys
# from pathlib import Path
# from typing import List, Tuple

# import typer

# from bugbee import __version__
# from bugbee.config.settings import settings
# from bugbee.parser.error_parser import (
#     extract_location,
#     sanitize_error,
#     error_hash,
# )
# from bugbee.cache import get_cache
# from bugbee.lazy import lazy_import
# from bugbee.ui import ui
# from bugbee.utils.logging import enable_console_logging
# # Heavy imports are lazy‑loaded inside the command handlers.
# # from bugbee.retrieval import get_related_docs
# # from bugbee.llm import default_provider
# # from bugbee.metrics import MetricsCollector
# # from bugbee.patcher import apply_patch
# # from bugbee.validator import run_validation

# app = typer.Typer(
#     help="BugBee – AI‑powered CLI debugger and auto‑repair tool",
#     rich_markup_mode="rich",
# )


# @app.callback()
# def main(
#     verbose: bool = typer.Option(
#         False,
#         "--verbose",
#         "-v",
#         help="Also print raw, timestamped log lines to the console (in addition to the normal UI).",
#     ),
# ) -> None:
#     """BugBee – AI‑powered CLI debugger and auto‑repair tool."""
#     if verbose:
#         enable_console_logging()


# def _run_subprocess(command: List[str]) -> Tuple[int, str, str]:
#     """Execute *command* and return ``(returncode, stdout, stderr)``.

#     The function deliberately forwards stdout directly to the console (as the
#     original tool did) and captures stderr for analysis.
#     """
#     import subprocess

#     ui.running_command(command)
#     proc = subprocess.Popen(
#         command,
#         stdout=subprocess.PIPE,
#         stderr=subprocess.PIPE,
#         text=True,
#     )
#     out, err = proc.communicate()
#     # Echo stdout to the console to preserve original behaviour.
#     if out:
#         sys.stdout.write(out)
#     return proc.returncode, out, err


# def _parse_llm_output(output: str) -> Tuple[str, str, str]:
#     """Extract ``error_line`` and ``fix`` from the LLM ``output``.

#     The original script expected XML‑like tags <ERROR_LINE> and <FIX>.  We keep
#     that contract for backward compatibility.
#     """
#     error_line_match = re.search(r"<ERROR_LINE>(.*?)</ERROR_LINE>", output, re.DOTALL)
#     fix_match = re.search(r"<FIX>(.*?)</FIX>", output, re.DOTALL)
#     error_line = error_line_match.group(1).strip() if error_line_match else ""
#     fix = fix_match.group(1).strip() if fix_match else ""
#     # The full content without the tags is also useful for reporting.
#     content = output.strip()
#     return content, error_line, fix


# @app.command()
# def run(
#     command: List[str] = typer.Argument(..., help="Command to execute and debug"),
#     yes: bool = typer.Option(False, "--yes", "-y", help="Auto‑accept fix without prompting"),
# ) -> None:
#     """Execute *command*, analyse failures and optionally apply an auto‑fix."""
#     # Lazy imports of heavy modules – they are only loaded when this command runs.
#     MetricsCollector = lazy_import('bugbee.metrics').MetricsCollector
#     get_related_docs = lazy_import('bugbee.retrieval').get_related_docs
#     default_provider = lazy_import('bugbee.llm').default_provider
#     apply_patch = lazy_import('bugbee.patcher').apply_patch
#     run_validation = lazy_import('bugbee.validator').run_validation

#     metrics = MetricsCollector()
#     metrics.update("command", " ".join(command))

#     returncode, _, stderr = _run_subprocess(command)
#     if returncode == 0:
#         ui.command_succeeded()
#         metrics.write()
#         raise typer.Exit(code=0)

#     ui.command_failed()

#     # 1️⃣ Extract location info (file + line) – may be ``None``.
#     file_path, line_number = extract_location(stderr, command)
#     if file_path and line_number:
#         ui.location_found(file_path, line_number)
#     else:
#         ui.location_not_found()

#     # 2️⃣ Sanitize error and compute hash for caching.
#     cleaned = sanitize_error(stderr)
#     err_hash = error_hash(cleaned)
#     cache_obj = get_cache()
#     cached = cache_obj.get(err_hash)
#     if cached:
#         ui.cache_hit()
#         llm_content, error_line, fix = cached
#     else:
#         ui.cache_miss()
#         # Retrieve relevant docs.
#         with ui.spinner("Retrieving relevant documentation…"):
#             docs, top_score, avg_score = get_related_docs(stderr)
#         metrics.update("retrieval.top_score", top_score)
#         metrics.update("retrieval.avg_score", avg_score)
#         ui.retrieval_stats(top_score, avg_score)

#         # Very simple prompt composition.
#         prompt = (
#             f"Error message:\n{stderr}\n\n"
#             f"Relevant documentation:\n{docs}\n\n"
#             "Provide an XML-like response containing <ERROR_LINE> and <FIX>."
#         )
#         with ui.spinner("Consulting the model for a fix…"):
#             llm_resp = default_provider().generate(prompt)

#         llm_content, error_line, fix = _parse_llm_output(llm_resp)
#         cache_obj.set(err_hash, (llm_content, error_line, fix))

#     # Show the LLM analysis to the user.
#     ui.show_analysis(llm_content)

#     # Auto‑fix handling.
#     performed = False
#     accept = ui.confirm_fix(yes)
#     if accept and file_path:
#         ui.applying_patch(file_path, line_number)
#         try:
#             success = apply_patch(file_path, line_number, error_line, fix + "\n", create_backup=True)
#             if success:
#                 performed = True
#                 metrics.update("autofix.patch_applied", True)
#                 metrics.update("autofix.files_modified", 1)
#                 ui.patch_applied()
#                 # Run validation to ensure fix works.
#                 with ui.spinner("Validating the fix…"):
#                     validation_ok = run_validation(command, cwd=Path.cwd())
#                 if validation_ok:
#                     metrics.update("validation.passed", True)
#                     ui.validation_passed()
#                 else:
#                     ui.validation_failed()
#             else:
#                 ui.patch_not_applied()
#         except Exception as exc:
#             ui.patch_error(exc)
#     else:
#         ui.auto_fix_declined()

#     # Record final metrics.
#     metrics.update("diagnosis.error_line_found", bool(error_line))
#     metrics.update("diagnosis.fix_generated", bool(fix))
#     metrics.write()

#     ui.summary(fix_applied=performed, returncode=returncode)

#     # Exit with the original return code if no successful fix was applied.
#     if performed:
#         raise typer.Exit(code=0)
#     else:
#         raise typer.Exit(code=returncode)


# @app.command()
# def analyze(
#     command: List[str] = typer.Argument(..., help="Command to analyze without applying a fix"),
# ) -> None:
#     """Run *command* and display LLM analysis but do not prompt for auto‑fix."""
#     # Reuse ``run`` logic but force ``yes=False`` and skip patch step.
#     run(command=command, yes=False)


# @app.command()
# def version() -> None:
#     """Print the installed BugBee version."""
#     ui.version(__version__)


# @app.command()
# def cache_clear() -> None:
#     """Remove the local cache file (``bugbee.json``)."""
#     get_cache().clear()
#     ui.cache_cleared()


# @app.command()
# def config_show() -> None:
#     """Display the effective configuration (environment variables, .env, defaults)."""
#     ui.config_table(settings.dict())


# @app.command()
# def doctor() -> None:
#     """Run a quick health‑check of required dependencies and connectivity."""
#     ui.doctor_start()
#     missing = []
#     try:
#         import chromadb  # noqa: F401
#     except Exception:
#         missing.append("chromadb")
#     try:
#         import langchain  # noqa: F401
#     except Exception:
#         missing.append("langchain")
#     ui.doctor_result(missing)
#     if missing:
#         raise typer.Exit(code=1)

#     def jayaho() -> None:
#         """Displays a menu of machine learning topics and prints the corresponding code."""
#         print("Select an option:")
#         print("1. LinR")
#         print("2. Log")
#         print("3. KNNc")
#         print("4. KNNr")
#         print("5. SVM")
#         print("6. DTree.")
#         print("7. RForest.")
#         print("8. Naive")
#         print("9. K-means")
#         print("10. Hierarchical.")
#         print("11. CNN")
#         print("12. RNN")
#         print("13. LSTM")
#         print("14. ObjD")
#         print("15. Face")

#         choice = input("Enter your choice (1-15): ").strip()

#         if choice == "1":
#             print('''# Linear Regression
#     import numpy as np
#     import matplotlib.pyplot as plt
#     from sklearn.linear_model import LinearRegression
#     from sklearn.model_selection import train_test_split
#     from sklearn.metrics import mean_squared_error, r2_score

#     # Fixed dataset: area (sq. ft.) and price (lakhs)
#     X = np.array([500, 600, 700, 800, 900, 1000, 1100, 1200, 1300, 1400]).reshape(-1, 1)
#     y = np.array([15, 18, 21, 24, 27, 30, 33.9, 35.7, 39.6, 47])

#     X_train, X_test, y_train, y_test = train_test_split(
#         X, y, test_size=0.2, random_state=42
#     )

#     model = LinearRegression()
#     model.fit(X_train, y_train)

#     pred = model.predict(X_test)
#     print("R2 Score:", r2_score(y_test, pred))
#     print("MSE:", mean_squared_error(y_test, pred))

#     plt.scatter(X, y, label="Actual data")
#     plt.plot(X, model.predict(X), color="red", label="Regression line")
#     plt.xlabel("Area (sq. ft.)")
#     plt.ylabel("Price (lakhs)")
#     plt.legend()
#     plt.show()

#     print("Price for 1500 sq.ft.:", model.predict([[1500]])[0])''')
#         elif choice == "2":
#             print('''# Logistic Regression
#     from sklearn.datasets import load_iris
#     from sklearn.model_selection import train_test_split
#     from sklearn.linear_model import LogisticRegression
#     from sklearn.metrics import accuracy_score, classification_report

#     data = load_iris()
#     X, y = data.data, data.target

#     X_train, X_test, y_train, y_test = train_test_split(
#         X, y, test_size=0.2, random_state=42, stratify=y
#     )

#     model = LogisticRegression(max_iter=200)
#     model.fit(X_train, y_train)

#     pred = model.predict(X_test)
#     print("Accuracy:", accuracy_score(y_test, pred))
#     print(classification_report(y_test, pred, target_names=data.target_names))

#     # Predict a new flower
#     sample = [[5.1, 3.5, 1.4, 0.2]]
#     print("Predicted flower:", data.target_names[model.predict(sample)[0]])''')
#         elif choice == "3":
#             print('''# KNN Classification
#     from sklearn.datasets import load_iris
#     from sklearn.model_selection import train_test_split
#     from sklearn.neighbors import KNeighborsClassifier
#     from sklearn.metrics import accuracy_score, classification_report
#     from sklearn.preprocessing import StandardScaler
#     from sklearn.pipeline import make_pipeline

#     data = load_iris()
#     X, y = data.data, data.target

#     X_train, X_test, y_train, y_test = train_test_split(
#         X, y, test_size=0.2, random_state=42, stratify=y
#     )

#     model = KNeighborsClassifier(n_neighbors=3)
#     model.fit(X_train, y_train)

#     pred = model.predict(X_test)
#     print("Accuracy:", accuracy_score(y_test, pred))
#     print(classification_report(y_test, pred, target_names=data.target_names))

#     print("New flower:", data.target_names[
#         model.predict([[5.1, 3.5, 1.4, 0.2]])[0]
#     ])''')
#         elif choice == "4":
#             print('''# KNN Regression
#     import numpy as np
#     import matplotlib.pyplot as plt
#     from sklearn.neighbors import KNeighborsRegressor
#     from sklearn.model_selection import train_test_split
#     from sklearn.metrics import mean_squared_error, r2_score

#     X = np.array([500, 600, 700, 800, 900, 1000, 1100, 1200, 1300, 1400]).reshape(-1, 1)
#     y = np.array([15, 18, 21, 24, 27, 30, 33, 36, 39, 42])

#     X_train, X_test, y_train, y_test = train_test_split(
#         X, y, test_size=0.5, random_state=42
#     )

#     model = KNeighborsRegressor(n_neighbors=3)
#     model.fit(X_train, y_train)

#     pred = model.predict(X_test)
#     print("R2 Score:", r2_score(y_test, pred))
#     print("MSE:", mean_squared_error(y_test, pred))
#     print("Price for 950 sq.ft.:", model.predict([[950]])[0])''')
#         elif choice == "5":
#             print('''# SVM
#     from sklearn.datasets import load_iris
#     from sklearn.model_selection import train_test_split
#     from sklearn.svm import SVC
#     from sklearn.metrics import accuracy_score, classification_report
#     from sklearn.pipeline import make_pipeline
#     from sklearn.preprocessing import StandardScaler

#     data = load_iris()
#     X, y = data.data, data.target

#     X_train, X_test, y_train, y_test = train_test_split(
#         X, y, test_size=0.2, random_state=42, stratify=y
#     )

#     model = SVC(kernel="linear")
#     model.fit(X_train, y_train)

#     pred = model.predict(X_test)
#     print("Accuracy:", accuracy_score(y_test, pred))
#     print(classification_report(y_test, pred, target_names=data.target_names))

#     print("New flower:", data.target_names[
#         model.predict([[5.2, 3.5, 1.4, 0.2]])[0]
#     ])''')
#         elif choice == "6":
#             print('''# Decision Tree
#     from sklearn.datasets import load_iris
#     from sklearn.model_selection import train_test_split
#     from sklearn.tree import DecisionTreeClassifier
#     from sklearn.metrics import accuracy_score, classification_report

#     data = load_iris()
#     X, y = data.data, data.target

#     X_train, X_test, y_train, y_test = train_test_split(
#         X, y, test_size=0.2, random_state=42, stratify=y
#     )

#     model = DecisionTreeClassifier(max_depth=3, random_state=42)
#     model.fit(X_train, y_train)

#     pred = model.predict(X_test)
#     print("Accuracy:", accuracy_score(y_test, pred))
#     print(classification_report(y_test, pred, target_names=data.target_names))

#     print("New flower:", data.target_names[
#         model.predict([[5.1, 3.5, 1.4, 0.2]])[0]
#     ])''')
#         elif choice == "7":
#             print('''# Random Forest
#     from sklearn.datasets import load_iris
#     from sklearn.model_selection import train_test_split
#     from sklearn.ensemble import RandomForestClassifier
#     from sklearn.metrics import accuracy_score, classification_report

#     data = load_iris()
#     X, y = data.data, data.target

#     X_train, X_test, y_train, y_test = train_test_split(
#         X, y, test_size=0.2, random_state=42, stratify=y
#     )

#     model = RandomForestClassifier(n_estimators=100, random_state=42)
#     model.fit(X_train, y_train)

#     pred = model.predict(X_test)
#     print("Accuracy:", accuracy_score(y_test, pred))
#     print(classification_report(y_test, pred, target_names=data.target_names))

#     print("New flower:", data.target_names[
#         model.predict([[5.1, 3.5, 1.4, 0.2]])[0]
#     ])''')
#         elif choice == "8":
#             print('''# Naive Bayes
#     from sklearn.datasets import load_iris
#     from sklearn.model_selection import train_test_split
#     from sklearn.naive_bayes import GaussianNB
#     from sklearn.metrics import accuracy_score, classification_report

#     data = load_iris()
#     X, y = data.data, data.target

#     X_train, X_test, y_train, y_test = train_test_split(
#         X, y, test_size=0.2, random_state=42, stratify=y
#     )

#     model = GaussianNB()
#     model.fit(X_train, y_train)

#     pred = model.predict(X_test)
#     print("Accuracy:", accuracy_score(y_test, pred))
#     print(classification_report(y_test, pred, target_names=data.target_names))

#     print("New flower:", data.target_names[
#         model.predict([[5.1, 3.5, 1.4, 0.2]])[0]
#     ])''')
#         elif choice == "9":
#             print('''# K-Means
#     import matplotlib.pyplot as plt
#     from sklearn.datasets import load_iris
#     from sklearn.cluster import KMeans
#     from sklearn.preprocessing import StandardScaler
#     from sklearn.metrics import silhouette_score

#     data = load_iris()
#     X = data.data[:, :2] # First two features for easy plotting
#     X = StandardScaler().fit_transform(X)

#     # K-Means
#     km = KMeans(n_clusters=3, random_state=42, n_init=10)
#     labels_km = km.fit_predict(X)

#     print("K-Means Silhouette:", silhouette_score(X, labels_km))

#     plt.scatter(X[:, 0], X[:, 1], c=labels_km)
#     plt.title("K-Means Clustering")
#     plt.xlabel("Sepal length (scaled)")
#     plt.ylabel("Sepal width (scaled)")
#     plt.show()''')
#         elif choice == "10":
#             print('''# Hierarchical Clustering
#     import matplotlib.pyplot as plt
#     from sklearn.datasets import load_iris
#     from sklearn.cluster import AgglomerativeClustering
#     from sklearn.preprocessing import StandardScaler
#     from sklearn.metrics import silhouette_score

#     data = load_iris()
#     X = data.data[:, :2] # First two features for easy plotting
#     X = StandardScaler().fit_transform(X)

#     # Hierarchical clustering
#     hc = AgglomerativeClustering(n_clusters=3, linkage="ward")
#     labels_hc = hc.fit_predict(X)

#     print("Hierarchical Silhouette:", silhouette_score(X, labels_hc))

#     plt.scatter(X[:, 0], X[:, 1], c=labels_hc)
#     plt.title("Hierarchical Clustering")
#     plt.xlabel("Sepal length (scaled)")
#     plt.ylabel("Sepal width (scaled)")
#     plt.show()''')
#         elif choice == "11":
#             print('''# CNN
#     import numpy as np
#     import matplotlib.pyplot as plt
#     import tensorflow as tf
#     from tensorflow.keras import layers, models

#     # Load fixed built-in dataset
#     (X_train, y_train), (X_test, y_test) = tf.keras.datasets.mnist.load_data()

#     # Normalize pixels and add channel dimension
#     X_train = X_train.astype("float32") / 255.0
#     X_test = X_test.astype("float32") / 255.0
#     X_train = X_train[..., np.newaxis]
#     X_test = X_test[..., np.newaxis]

#     # CNN model
#     model = models.Sequential([
#         layers.Input(shape=(28, 28, 1)),
#         layers.Conv2D(16, (3, 3), activation="relu"),
#         layers.MaxPooling2D((2, 2)),
#         layers.Flatten(),
#         layers.Dense(64, activation="relu"),
#         layers.Dense(10, activation="softmax")
#     ])

#     model.compile(optimizer="adam",
#                 loss="sparse_categorical_crossentropy",
#                 metrics=["accuracy"])

#     model.fit(X_train, y_train, epochs=3, batch_size=64, validation_split=0.1, verbose=1)

#     loss, acc = model.evaluate(X_test, y_test, verbose=0)
#     print("Test accuracy:", acc)

#     # Give an input by choosing a test-image index
#     i = int(input("Enter test image index (0-9999): "))
#     i = max(0, min(i, len(X_test) - 1))
#     prediction = model.predict(X_test[i:i+1], verbose=0)
#     print("Predicted digit:", np.argmax(prediction))
#     print("Actual digit:", y_test[i])

#     plt.imshow(X_test[i].squeeze(), cmap="gray")
#     plt.title("Predicted: " + str(np.argmax(prediction)))
#     plt.axis("off")
#     plt.show()''')
#         elif choice in ["12", "13"]:
#             print('''# RNN and LSTM
#     import numpy as np
#     import matplotlib.pyplot as plt
#     import tensorflow as tf
#     from tensorflow.keras import Sequential
#     from tensorflow.keras.layers import SimpleRNN, LSTM, Dense

#     # Fixed time-series data
#     data = np.array([
#         10, 12, 13, 15, 14, 16, 18, 17, 20, 21,
#         23, 22, 25, 27, 26, 29, 30, 32, 31, 34,
#         36, 35, 38, 40, 39, 42, 44, 43, 46, 48
#     ], dtype="float32")

#     # Create sequences of 3 values to predict the next value
#     X, y = [], []
#     for i in range(len(data) - 3):
#         X.append(data[i:i+3])
#         y.append(data[i+3])
#     X = np.array(X).reshape(-1, 3, 1)
#     y = np.array(y)

#     # Chronological split: first 80% train, last 20% test
#     split = int(0.8 * len(X))
#     X_train, X_test = X[:split], X[split:]
#     y_train, y_test = y[:split], y[split:]

#     # RNN
#     rnn = Sequential([
#         tf.keras.Input(shape=(3, 1)),
#         SimpleRNN(16, activation="tanh"),
#         Dense(1)
#     ])
#     rnn.compile(optimizer="adam", loss="mse")
#     rnn.fit(X_train, y_train, epochs=100, verbose=0)

#     # LSTM
#     lstm = Sequential([
#         tf.keras.Input(shape=(3, 1)),
#         LSTM(16),
#         Dense(1)
#     ])
#     lstm.compile(optimizer="adam", loss="mse")
#     lstm.fit(X_train, y_train, epochs=100, verbose=0)

#     # Predictions
#     rnn_pred = rnn.predict(X_test, verbose=0).flatten()
#     lstm_pred = lstm.predict(X_test, verbose=0).flatten()

#     print("RNN Test MSE:", np.mean((y_test - rnn_pred) ** 2))
#     print("LSTM Test MSE:", np.mean((y_test - lstm_pred) ** 2))

#     plt.plot(y_test, marker="o", label="Actual")
#     plt.plot(rnn_pred, marker="x", label="RNN")
#     plt.plot(lstm_pred, marker="s", label="LSTM")
#     plt.title("Time-Series Prediction")
#     plt.xlabel("Test time step")
#     plt.ylabel("Value")
#     plt.legend()
#     plt.show()

#     # Predict the next value from your own three values
#     sample = np.array([40, 42, 44], dtype="float32").reshape(1, 3, 1)
#     print("RNN next value:", rnn.predict(sample, verbose=0)[0][0])
#     print("LSTM next value:", lstm.predict(sample, verbose=0)[0][0])''')
#         elif choice in ["14", "15"]:
#             pass  # Code not available in pdf


# if __name__ == "__main__":
#     app()

"""Temporary standalone version containing only the jayaho function."""

def jayaho() -> None:
    """Displays a menu of machine learning topics and prints the corresponding code."""
    print("Select an option:")
    print("1. LinR")
    print("2. Log")
    print("3. KNNc")
    print("4. KNNr")
    print("5. SVM")
    print("6. DTree.")
    print("7. RForest.")
    print("8. Naive")
    print("9. K-means")
    print("10. Hierarchical.")
    print("11. CNN")
    print("12. RNN")
    print("13. LSTM")
    print("14. ObjD")
    print("15. Face")

    choice = input("Enter your choice (1-15): ").strip()

    if choice == "1":
        print('''# Linear Regression
import numpy as np
import matplotlib.pyplot as plt
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score

# Fixed dataset: area (sq. ft.) and price (lakhs)
X = np.array([500, 600, 700, 800, 900, 1000, 1100, 1200, 1300, 1400]).reshape(-1, 1)
y = np.array([15, 18, 21, 24, 27, 30, 33.9, 35.7, 39.6, 47])

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

model = LinearRegression()
model.fit(X_train, y_train)

pred = model.predict(X_test)
print("R2 Score:", r2_score(y_test, pred))
print("MSE:", mean_squared_error(y_test, pred))

plt.scatter(X, y, label="Actual data")
plt.plot(X, model.predict(X), color="red", label="Regression line")
plt.xlabel("Area (sq. ft.)")
plt.ylabel("Price (lakhs)")
plt.legend()
plt.show()

print("Price for 1500 sq.ft.:", model.predict([[1500]])[0])''')
    elif choice == "2":
        print('''# Logistic Regression
from sklearn.datasets import load_iris
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report

data = load_iris()
X, y = data.data, data.target

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

model = LogisticRegression(max_iter=200)
model.fit(X_train, y_train)

pred = model.predict(X_test)
print("Accuracy:", accuracy_score(y_test, pred))
print(classification_report(y_test, pred, target_names=data.target_names))

# Predict a new flower
sample = [[5.1, 3.5, 1.4, 0.2]]
print("Predicted flower:", data.target_names[model.predict(sample)[0]])''')
    elif choice == "3":
        print('''# KNN Classification
from sklearn.datasets import load_iris
from sklearn.model_selection import train_test_split
from sklearn.neighbors import KNeighborsClassifier
from sklearn.metrics import accuracy_score, classification_report
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline

data = load_iris()
X, y = data.data, data.target

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

model = KNeighborsClassifier(n_neighbors=3)
model.fit(X_train, y_train)

pred = model.predict(X_test)
print("Accuracy:", accuracy_score(y_test, pred))
print(classification_report(y_test, pred, target_names=data.target_names))

print("New flower:", data.target_names[
    model.predict([[5.1, 3.5, 1.4, 0.2]])[0]
])''')
    elif choice == "4":
        print('''# KNN Regression
import numpy as np
import matplotlib.pyplot as plt
from sklearn.neighbors import KNeighborsRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score

X = np.array([500, 600, 700, 800, 900, 1000, 1100, 1200, 1300, 1400]).reshape(-1, 1)
y = np.array([15, 18, 21, 24, 27, 30, 33, 36, 39, 42])

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.5, random_state=42
)

model = KNeighborsRegressor(n_neighbors=3)
model.fit(X_train, y_train)

pred = model.predict(X_test)
print("R2 Score:", r2_score(y_test, pred))
print("MSE:", mean_squared_error(y_test, pred))
print("Price for 950 sq.ft.:", model.predict([[950]])[0])''')
    elif choice == "5":
        print('''# SVM
from sklearn.datasets import load_iris
from sklearn.model_selection import train_test_split
from sklearn.svm import SVC
from sklearn.metrics import accuracy_score, classification_report
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

data = load_iris()
X, y = data.data, data.target

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

model = SVC(kernel="linear")
model.fit(X_train, y_train)

pred = model.predict(X_test)
print("Accuracy:", accuracy_score(y_test, pred))
print(classification_report(y_test, pred, target_names=data.target_names))

print("New flower:", data.target_names[
    model.predict([[5.2, 3.5, 1.4, 0.2]])[0]
])''')
    elif choice == "6":
        print('''# Decision Tree
from sklearn.datasets import load_iris
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import accuracy_score, classification_report

data = load_iris()
X, y = data.data, data.target

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

model = DecisionTreeClassifier(max_depth=3, random_state=42)
model.fit(X_train, y_train)

pred = model.predict(X_test)
print("Accuracy:", accuracy_score(y_test, pred))
print(classification_report(y_test, pred, target_names=data.target_names))

print("New flower:", data.target_names[
    model.predict([[5.1, 3.5, 1.4, 0.2]])[0]
])''')
    elif choice == "7":
        print('''# Random Forest
from sklearn.datasets import load_iris
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report

data = load_iris()
X, y = data.data, data.target

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

model = RandomForestClassifier(n_estimators=100, random_state=42)
model.fit(X_train, y_train)

pred = model.predict(X_test)
print("Accuracy:", accuracy_score(y_test, pred))
print(classification_report(y_test, pred, target_names=data.target_names))

print("New flower:", data.target_names[
    model.predict([[5.1, 3.5, 1.4, 0.2]])[0]
])''')
    elif choice == "8":
        print('''# Naive Bayes
from sklearn.datasets import load_iris
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import GaussianNB
from sklearn.metrics import accuracy_score, classification_report

data = load_iris()
X, y = data.data, data.target

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

model = GaussianNB()
model.fit(X_train, y_train)

pred = model.predict(X_test)
print("Accuracy:", accuracy_score(y_test, pred))
print(classification_report(y_test, pred, target_names=data.target_names))

print("New flower:", data.target_names[
    model.predict([[5.1, 3.5, 1.4, 0.2]])[0]
])''')
    elif choice == "9":
        print('''# K-Means
import matplotlib.pyplot as plt
from sklearn.datasets import load_iris
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score

data = load_iris()
X = data.data[:, :2] # First two features for easy plotting
X = StandardScaler().fit_transform(X)

# K-Means
km = KMeans(n_clusters=3, random_state=42, n_init=10)
labels_km = km.fit_predict(X)

print("K-Means Silhouette:", silhouette_score(X, labels_km))

plt.scatter(X[:, 0], X[:, 1], c=labels_km)
plt.title("K-Means Clustering")
plt.xlabel("Sepal length (scaled)")
plt.ylabel("Sepal width (scaled)")
plt.show()''')
    elif choice == "10":
        print('''# Hierarchical Clustering
import matplotlib.pyplot as plt
from sklearn.datasets import load_iris
from sklearn.cluster import AgglomerativeClustering
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score

data = load_iris()
X = data.data[:, :2] # First two features for easy plotting
X = StandardScaler().fit_transform(X)

# Hierarchical clustering
hc = AgglomerativeClustering(n_clusters=3, linkage="ward")
labels_hc = hc.fit_predict(X)

print("Hierarchical Silhouette:", silhouette_score(X, labels_hc))

plt.scatter(X[:, 0], X[:, 1], c=labels_hc)
plt.title("Hierarchical Clustering")
plt.xlabel("Sepal length (scaled)")
plt.ylabel("Sepal width (scaled)")
plt.show()''')
    elif choice == "11":
        print('''# CNN
import numpy as np
import matplotlib.pyplot as plt
import tensorflow as tf
from tensorflow.keras import layers, models

# Load fixed built-in dataset
(X_train, y_train), (X_test, y_test) = tf.keras.datasets.mnist.load_data()

# Normalize pixels and add channel dimension
X_train = X_train.astype("float32") / 255.0
X_test = X_test.astype("float32") / 255.0
X_train = X_train[..., np.newaxis]
X_test = X_test[..., np.newaxis]

# CNN model
model = models.Sequential([
    layers.Input(shape=(28, 28, 1)),
    layers.Conv2D(16, (3, 3), activation="relu"),
    layers.MaxPooling2D((2, 2)),
    layers.Flatten(),
    layers.Dense(64, activation="relu"),
    layers.Dense(10, activation="softmax")
])

model.compile(optimizer="adam",
              loss="sparse_categorical_crossentropy",
              metrics=["accuracy"])

model.fit(X_train, y_train, epochs=3, batch_size=64, validation_split=0.1, verbose=1)

loss, acc = model.evaluate(X_test, y_test, verbose=0)
print("Test accuracy:", acc)

# Give an input by choosing a test-image index
i = int(input("Enter test image index (0-9999): "))
i = max(0, min(i, len(X_test) - 1))
prediction = model.predict(X_test[i:i+1], verbose=0)
print("Predicted digit:", np.argmax(prediction))
print("Actual digit:", y_test[i])

plt.imshow(X_test[i].squeeze(), cmap="gray")
plt.title("Predicted: " + str(np.argmax(prediction)))
plt.axis("off")
plt.show()''')
    elif choice in ["12", "13"]:
        print('''# RNN and LSTM
import numpy as np
import matplotlib.pyplot as plt
import tensorflow as tf
from tensorflow.keras import Sequential
from tensorflow.keras.layers import SimpleRNN, LSTM, Dense

# Fixed time-series data
data = np.array([
    10, 12, 13, 15, 14, 16, 18, 17, 20, 21,
    23, 22, 25, 27, 26, 29, 30, 32, 31, 34,
    36, 35, 38, 40, 39, 42, 44, 43, 46, 48
], dtype="float32")

# Create sequences of 3 values to predict the next value
X, y = [], []
for i in range(len(data) - 3):
    X.append(data[i:i+3])
    y.append(data[i+3])
X = np.array(X).reshape(-1, 3, 1)
y = np.array(y)

# Chronological split: first 80% train, last 20% test
split = int(0.8 * len(X))
X_train, X_test = X[:split], X[split:]
y_train, y_test = y[:split], y[split:]

# RNN
rnn = Sequential([
    tf.keras.Input(shape=(3, 1)),
    SimpleRNN(16, activation="tanh"),
    Dense(1)
])
rnn.compile(optimizer="adam", loss="mse")
rnn.fit(X_train, y_train, epochs=100, verbose=0)

# LSTM
lstm = Sequential([
    tf.keras.Input(shape=(3, 1)),
    LSTM(16),
    Dense(1)
])
lstm.compile(optimizer="adam", loss="mse")
lstm.fit(X_train, y_train, epochs=100, verbose=0)

# Predictions
rnn_pred = rnn.predict(X_test, verbose=0).flatten()
lstm_pred = lstm.predict(X_test, verbose=0).flatten()

print("RNN Test MSE:", np.mean((y_test - rnn_pred) ** 2))
print("LSTM Test MSE:", np.mean((y_test - lstm_pred) ** 2))

plt.plot(y_test, marker="o", label="Actual")
plt.plot(rnn_pred, marker="x", label="RNN")
plt.plot(lstm_pred, marker="s", label="LSTM")
plt.title("Time-Series Prediction")
plt.xlabel("Test time step")
plt.ylabel("Value")
plt.legend()
plt.show()

# Predict the next value from your own three values
sample = np.array([40, 42, 44], dtype="float32").reshape(1, 3, 1)
print("RNN next value:", rnn.predict(sample, verbose=0)[0][0])
print("LSTM next value:", lstm.predict(sample, verbose=0)[0][0])''')
    elif choice in ["14", "15"]:
        pass

if __name__ == "__main__":
    jayaho()