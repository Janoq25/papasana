"""Carga local y transformaciones aplicadas después de separar los grupos."""

from pathlib import Path

from PIL import Image
from torch.utils.data import Dataset
from torchvision import transforms

from potato_blight import CLASSES
from potato_blight.models.architectures import IMAGENET_MEAN, IMAGENET_STD


def eval_transform(img_size: int):
    return transforms.Compose([transforms.Resize(int(img_size / 0.875)), transforms.CenterCrop(img_size),
                               transforms.ToTensor(), transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD)])


def train_transform(img_size: int):
    return transforms.Compose([transforms.RandomResizedCrop(img_size, scale=(0.75, 1.0)),
                               transforms.RandomHorizontalFlip(), transforms.RandomVerticalFlip(),
                               transforms.RandomRotation(15), transforms.ColorJitter(0.15, 0.15, 0.15, 0.03),
                               transforms.ToTensor(), transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD)])


class ManifestDataset(Dataset):
    def __init__(self, df, roots: dict[str, str], transform):
        self.df = df.reset_index(drop=True)
        self.roots = {key: Path(value).resolve() for key, value in roots.items()}
        self.transform = transform

    def __len__(self):
        return len(self.df)

    def __getitem__(self, index):
        row = self.df.iloc[index]
        root = self.roots[row["dataset_id"]]
        path = (root / row["path"]).resolve()
        if not path.is_relative_to(root):
            raise ValueError("Imagen fuera de la raíz autorizada")
        with Image.open(path) as image:
            tensor = self.transform(image.convert("RGB"))
        return tensor, CLASSES.index(row["label"]), row["path"]
