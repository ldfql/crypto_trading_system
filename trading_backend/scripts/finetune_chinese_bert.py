import os
import json
import logging
import random
import numpy as np
import torch
from transformers import (
    BertTokenizer,
    BertForSequenceClassification,
    TrainingArguments,
    Trainer,
    DataCollatorWithPadding,
    EarlyStoppingCallback
)
from torch.utils.data import Dataset
from sklearn.model_selection import train_test_split
from torch.nn.utils import clip_grad_norm_
from app.data.financial_terms_dict import FINANCIAL_TERMS_DICT

class FinancialDataset(Dataset):
    def __init__(self, texts, labels, tokenizer, max_length=128):
        self.encodings = tokenizer(texts, truncation=True, padding=True, max_length=max_length)
        self.labels = labels

    def __getitem__(self, idx):
        item = {key: torch.tensor(val[idx]) for key, val in self.encodings.items()}
        item['labels'] = torch.tensor(self.labels[idx])
        return item

    def __len__(self):
        return len(self.labels)

def load_financial_data(data_path):
    """Load financial sentiment data."""
    with open(data_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    texts = []
    labels = []

    # Process both training and validation data
    for dataset in ['training_data', 'validation_data']:
        for item in data[dataset]:
            texts.append(item['text'])
            sentiment_map = {'bearish': 0, 'bullish': 1, 'neutral': 2}
            labels.append(sentiment_map[item['label'].lower()])

    return texts, labels

def augment_text(text, num_augmentations=7):
    """Enhanced text augmentation with more sophisticated techniques."""
    augmented_texts = []

    # Original text is always included
    augmented_texts.append(text)

    for _ in range(num_augmentations):
        augmented = text

        # Synonym replacement (using predefined financial terms)
        if random.random() < 0.7:
            words = augmented.split()
            for i in range(len(words)):
                if words[i] in FINANCIAL_TERMS_DICT:
                    if random.random() < 0.3:
                        words[i] = random.choice(FINANCIAL_TERMS_DICT[words[i]])
            augmented = ' '.join(words)

        # Back translation augmentation simulation
        if random.random() < 0.5:
            words = augmented.split()
            random.shuffle(words)
            augmented = ' '.join(words)

        # Add noise
        if random.random() < 0.3:
            chars = list(augmented)
            for i in range(len(chars)):
                if random.random() < 0.1:
                    chars[i] = random.choice(chars)
            augmented = ''.join(chars)

        augmented_texts.append(augmented)

    return list(set(augmented_texts))  # Remove duplicates

def compute_metrics(eval_pred):
    """Compute metrics for evaluation."""
    predictions, labels = eval_pred
    predictions = np.argmax(predictions, axis=1)
    accuracy = np.mean(predictions == labels)

    # Calculate per-class metrics
    class_names = ['bearish', 'bullish', 'neutral']
    metrics = {'accuracy': accuracy}

    for i, class_name in enumerate(class_names):
        class_pred = predictions == i
        class_true = labels == i
        class_correct = (class_pred & class_true).sum()
        class_total = class_true.sum()
        if class_total > 0:
            class_accuracy = class_correct / class_total
            metrics[f'{class_name}_accuracy'] = class_accuracy

    return metrics

class WeightedTrainer(Trainer):
    """Custom trainer with weighted loss and gradient clipping."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_grad_norm = 1.0

    def compute_loss(self, model, inputs, return_outputs=False, num_items_in_batch=None):
        """
        Custom loss computation with class weights.
        """
        labels = inputs.pop("labels")
        outputs = model(**inputs)
        logits = outputs.logits

        loss_fct = torch.nn.CrossEntropyLoss(weight=class_weights)
        loss = loss_fct(logits.view(-1, model.config.num_labels), labels.view(-1))

        if num_items_in_batch is not None and self.args.gradient_accumulation_steps > 1:
            loss = loss / self.args.gradient_accumulation_steps

        return (loss, outputs) if return_outputs else loss

    def training_step(self, model, inputs, num_items_in_batch=None):
        """
        Perform a training step with gradient clipping.
        """
        model.train()
        inputs = self._prepare_inputs(inputs)

        with self.compute_loss_context_manager():
            loss = self.compute_loss(model, inputs, num_items_in_batch=num_items_in_batch)

        loss.backward()

        if self.args.max_grad_norm is not None and self.args.max_grad_norm > 0:
            clip_grad_norm_(model.parameters(), self.args.max_grad_norm)

        return loss.detach()

def main():
    """Main training function with enhanced configuration."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)

    # Set device and random seed
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    torch.manual_seed(42)
    np.random.seed(42)
    random.seed(42)
    logger.info(f"Using device: {device}")

    data_path = os.path.join("app", "data", "financial_sentiment_data_chinese.json")
    logger.info(f"Loading data from {data_path}")

    # Load and prepare data
    texts, labels = load_financial_data(data_path)
    logger.info(f"Loaded {len(texts)} samples")

    # Split data
    train_texts, eval_texts, train_labels, eval_labels = train_test_split(
        texts, labels, test_size=0.2, random_state=42, stratify=labels
    )
    logger.info(f"Training samples: {len(train_texts)}, Evaluation samples: {len(eval_texts)}")

    # Data augmentation for training set
    augmented_texts = []
    augmented_labels = []
    for text, label in zip(train_texts, train_labels):
        aug_texts = augment_text(text, num_augmentations=7)
        augmented_texts.extend(aug_texts)
        augmented_labels.extend([label] * len(aug_texts))
    logger.info(f"Augmented training samples: {len(augmented_texts)}")

    # Calculate class weights
    class_counts = np.bincount(augmented_labels)
    total_samples = len(augmented_labels)
    global class_weights
    class_weights = torch.FloatTensor([total_samples / (len(class_counts) * count) for count in class_counts])
    class_weights = class_weights.to(device)
    logger.info(f"Class weights: {class_weights}")

    # Load tokenizer and model
    tokenizer = BertTokenizer.from_pretrained("bert-base-chinese")
    model = BertForSequenceClassification.from_pretrained(
        "bert-base-chinese",
        num_labels=3,
        problem_type="single_label_classification"
    )
    model = model.to(device)

    # Create datasets
    train_dataset = FinancialDataset(augmented_texts, augmented_labels, tokenizer)
    eval_dataset = FinancialDataset(eval_texts, eval_labels, tokenizer)

    # Training arguments with optimized hyperparameters
    training_args = TrainingArguments(
        output_dir="results/chinese_bert_finetuned",
        num_train_epochs=15,
        per_device_train_batch_size=32,
        per_device_eval_batch_size=32,
        learning_rate=2e-5,
        weight_decay=0.02,
        evaluation_strategy="steps",
        eval_steps=25,
        save_strategy="steps",
        save_steps=25,
        load_best_model_at_end=True,
        metric_for_best_model="accuracy",
        greater_is_better=True,
        warmup_ratio=0.15,
        logging_dir="logs",
        logging_steps=5,
        seed=42,
        fp16=torch.cuda.is_available(),
        gradient_accumulation_steps=4,
        gradient_checkpointing=True
    )

    # Initialize trainer with improved early stopping
    trainer = WeightedTrainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        compute_metrics=compute_metrics,
        data_collator=DataCollatorWithPadding(tokenizer=tokenizer),
        callbacks=[
            EarlyStoppingCallback(
                early_stopping_patience=5,
                early_stopping_threshold=0.01
            )
        ]
    )

    try:
        logger.info("Starting training...")
        trainer.train()

        # Save the model
        model_save_path = os.path.join("models", "chinese_bert_finetuned")
        model.save_pretrained(model_save_path)
        tokenizer.save_pretrained(model_save_path)
        logger.info(f"Model saved to {model_save_path}")

        # Evaluate
        eval_results = trainer.evaluate()
        logger.info(f"Evaluation results: {eval_results}")

    except Exception as e:
        logger.error(f"Error in fine-tuning: {str(e)}")
        raise

if __name__ == "__main__":
    main()
