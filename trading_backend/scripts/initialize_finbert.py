"""Initialize and fine-tune FinBERT model for cryptocurrency sentiment analysis."""
import os
import json
import logging
import torch
from torch.utils.data import Dataset, DataLoader, random_split
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    Trainer,
    TrainingArguments,
    EarlyStoppingCallback,
)
from sklearn.metrics import accuracy_score, precision_recall_fscore_support
import numpy as np
from typing import Dict, List, Tuple

# Set environment variable for tokenizer parallelism
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("training.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


class SentimentDataset(Dataset):
    """Custom dataset for sentiment analysis."""

    def __init__(
        self, texts: List[str], labels: List[int], tokenizer, max_length: int = 512
    ):
        self.encodings = tokenizer(
            texts,
            truncation=True,
            padding=True,
            max_length=max_length,
            return_tensors="pt",
        )
        self.labels = torch.tensor(labels)

    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        item = {key: val[idx].clone().detach() for key, val in self.encodings.items()}
        item["labels"] = self.labels[idx].clone().detach()
        return item

    def __len__(self) -> int:
        return len(self.labels)


def load_training_data(file_path: str) -> Tuple[List[str], List[int]]:
    """Load and prepare training data from JSON file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        texts = []
        labels = []
        label_map = {"bearish": 0, "neutral": 1, "bullish": 2}

        # Process training data
        for item in data.get("training_data", []):
            texts.append(item["text"])
            label = item["label"].lower()
            if label not in label_map:
                raise ValueError(f"Invalid label '{label}' in training data")
            labels.append(label_map[label])

        # Process validation data if available
        for item in data.get("validation_data", []):
            texts.append(item["text"])
            label = item["label"].lower()
            if label not in label_map:
                raise ValueError(f"Invalid label '{label}' in validation data")
            labels.append(label_map[label])

        if not texts:
            raise ValueError("No training examples found in data file")

        logger.info(f"Loaded {len(texts)} examples from {file_path}")
        label_distribution = {
            label: labels.count(idx) for label, idx in label_map.items()
        }
        logger.info(f"Label distribution: {label_distribution}")

        return texts, labels
    except Exception as e:
        logger.error(f"Error loading training data from {file_path}: {str(e)}")
        raise


def compute_metrics(pred) -> Dict[str, float]:
    """Compute accuracy metrics for model evaluation."""
    labels = pred.label_ids
    preds = pred.predictions.argmax(-1)

    accuracy = accuracy_score(labels, preds)
    precision, recall, f1, _ = precision_recall_fscore_support(
        labels, preds, average="weighted", zero_division=0
    )

    metrics = {"accuracy": accuracy, "precision": precision, "recall": recall, "f1": f1}

    logger.info(f"Evaluation metrics: {metrics}")
    return metrics


def initialize_model(language: str) -> float:
    """Initialize and fine-tune model for specified language."""
    try:
        # Set device and optimize for CPU training
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        if device.type == "cpu":
            torch.set_num_threads(os.cpu_count())
        logger.info(f"Using device: {device} with {os.cpu_count()} CPU threads")

        # Load model and tokenizer
        model_name = (
            "ProsusAI/finbert"
            if language == "english"
            else "hfl/chinese-roberta-wwm-ext-large"
        )
        logger.info(f"Loading {model_name} model and tokenizer...")

        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForSequenceClassification.from_pretrained(
            model_name, num_labels=3, problem_type="single_label_classification"
        ).to(device)

        # Load and prepare data
        data_path = os.path.join(
            os.path.dirname(__file__),
            f"../app/data/financial_sentiment_data_{language}.json",
        )
        texts, labels = load_training_data(data_path)

        # Create dataset with validation split
        dataset = SentimentDataset(texts, labels, tokenizer)
        train_size = int(0.8 * len(dataset))
        val_size = len(dataset) - train_size

        train_dataset, val_dataset = random_split(
            dataset, [train_size, val_size], generator=torch.Generator().manual_seed(42)
        )

        logger.info(f"Training set size: {train_size}, Validation set size: {val_size}")

        # Training arguments optimized for available hardware
        training_args = TrainingArguments(
            output_dir=f"./results/{language}_model",
            num_train_epochs=30,
            per_device_train_batch_size=4 if device.type == "cpu" else 8,
            per_device_eval_batch_size=4 if device.type == "cpu" else 8,
            learning_rate=2e-5,
            weight_decay=0.01,
            logging_dir=f"./logs/{language}",
            logging_steps=10,
            evaluation_strategy="steps",
            eval_steps=50,
            save_strategy="steps",
            save_steps=50,
            load_best_model_at_end=True,
            metric_for_best_model="accuracy",
            greater_is_better=True,
            save_total_limit=2,
            fp16=device.type == "cuda",
            dataloader_num_workers=0 if device.type == "cpu" else 2,
            gradient_accumulation_steps=4 if device.type == "cpu" else 1,
            warmup_steps=100,
            logging_first_step=True,
        )

        # Initialize trainer with early stopping
        trainer = Trainer(
            model=model,
            args=training_args,
            train_dataset=train_dataset,
            eval_dataset=val_dataset,
            compute_metrics=compute_metrics,
            callbacks=[EarlyStoppingCallback(early_stopping_patience=3)],
        )

        # Train and evaluate
        logger.info(f"Starting training for {language} model...")
        trainer.train()

        # Final evaluation
        eval_results = trainer.evaluate()
        logger.info(f"Final evaluation results for {language}: {eval_results}")

        if eval_results["eval_accuracy"] < 0.85:
            logger.error(
                f"Model accuracy {eval_results['eval_accuracy']:.2f} "
                "below required threshold of 0.85"
            )
            raise ValueError("Model failed to achieve required accuracy threshold")

        # Save model
        output_dir = os.path.join(
            os.path.dirname(__file__), f"../models/{language}_finbert"
        )
        os.makedirs(output_dir, exist_ok=True)
        trainer.save_model(output_dir)
        tokenizer.save_pretrained(output_dir)
        logger.info(f"Model saved to {output_dir}")

        return eval_results["eval_accuracy"]

    except Exception as e:
        logger.error(f"Error initializing {language} model: {str(e)}")
        raise


if __name__ == "__main__":
    try:
        # Initialize both models
        accuracies = {}
        for language in ["english", "chinese"]:
            logger.info(f"Initializing {language} model...")
            accuracy = initialize_model(language)
            accuracies[language] = accuracy
            logger.info(
                f"Completed initialization of {language} model "
                f"with accuracy: {accuracy:.4f}"
            )

        logger.info("Final accuracies:")
        for language, accuracy in accuracies.items():
            logger.info(f"{language}: {accuracy:.4f}")

    except Exception as e:
        logger.error(f"Fatal error during model initialization: {str(e)}")
        raise
