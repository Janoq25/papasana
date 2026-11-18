"""Arquitecturas admitidas para entrenamiento e inferencia de PapaSana.

Este módulo solo depende de torch y timm: lo usan el entrenamiento (`ml/`) y el servicio de inferencia
(`ml-service`, que lo copia al construir su imagen), de modo que ambos construyen exactamente la misma red.

| clave               | modelo                                                                    |
|---------------------|---------------------------------------------------------------------------|
| resnet50            | ResNet50                                                                  |
| efficientnet_b3     | EfficientNet-B3                                                           |
| convnext_tiny       | ConvNeXt-Tiny                                                             |
| cnn_vit             | H1: backbone CNN cuyos tokens espaciales pasan por un encoder Transformer |
| effnet_att_bilstm   | H2: EfficientNet → secuencia de parches → BiLSTM → atención (D-06)        |
"""

from dataclasses import dataclass

import timm
import torch
from torch import nn

ARCHITECTURES = (
    "resnet50", "efficientnet_b3", "convnext_tiny", "cnn_vit", "effnet_att_bilstm",
    "efficientnetv2_b0", "mobilenetv4_conv_medium", "efficientvit_b1",
)
QUICK_COMPARISON_ARCHITECTURES = ("resnet50", "efficientnetv2_b0", "mobilenetv4_conv_medium", "efficientvit_b1")
TIMM_MODELS = {
    "resnet50": "resnet50.a1_in1k", "efficientnet_b3": "efficientnet_b3", "convnext_tiny": "convnext_tiny",
    "efficientnetv2_b0": "tf_efficientnetv2_b0.in1k",
    "mobilenetv4_conv_medium": "mobilenetv4_conv_medium.e500_r224_in1k",
    "efficientvit_b1": "efficientvit_b1.r224_in1k",
}
PRETRAINED_REVISIONS = {
    "resnet50": "767268603ca0cb0bfe326fa87277f19c419566ef",
    "efficientnetv2_b0": "30b1df5883752d711e047538d9b01db797782818",
    "mobilenetv4_conv_medium": "02a09fbfb82b289e871ba8255f9da58c056fb13b",
    "efficientvit_b1": "cebc58510738e196c3cce3c3077dc8737973b7ba",
}
IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)


@dataclass(frozen=True)
class ArchSpec:
    key: str
    display_name: str
    default_img_size: int
    description: str


SPECS: dict[str, ArchSpec] = {
    "efficientnetv2_b0": ArchSpec("efficientnetv2_b0", "EfficientNetV2-B0", 224,
                                    "CNN ligera con bloques fused-MBConv y MBConv."),
    "mobilenetv4_conv_medium": ArchSpec("mobilenetv4_conv_medium", "MobileNetV4 Conv Medium", 224,
                                         "CNN móvil de capacidad intermedia con pesos ImageNet."),
    "efficientvit_b1": ArchSpec("efficientvit_b1", "EfficientViT-B1", 224,
                                 "Red de visión eficiente con atención lineal multiescala."),
    "resnet50": ArchSpec("resnet50", "ResNet50", 224, "Red residual de 50 capas (referencia)."),
    "efficientnet_b3": ArchSpec("efficientnet_b3", "EfficientNet-B3", 300, "Escalado compuesto, B3."),
    "convnext_tiny": ArchSpec("convnext_tiny", "ConvNeXt-Tiny", 224, "CNN modernizada al estilo Transformer."),
    "cnn_vit": ArchSpec("cnn_vit", "H1 · CNN-ViT híbrido", 224,
                        "Mapa de características de una CNN convertido en tokens y procesado por un encoder "
                        "Transformer con token de clase."),
    "effnet_att_bilstm": ArchSpec("effnet_att_bilstm", "H2 · EfficientNet-Atención-BiLSTM", 224,
                                  "La BiLSTM recorre la secuencia de parches del mapa de características de "
                                  "EfficientNet y una atención aditiva resume la secuencia (D-06)."),
}


class FeatureExtractor(nn.Module):
    """Envuelve un backbone de timm y devuelve su mapa de características (B, C, H, W).

    Es un módulo propio para que Grad-CAM pueda registrar un hook sobre su salida.
    """

    def __init__(self, name: str, pretrained: bool):
        super().__init__()
        self.backbone = timm.create_model(name, pretrained=pretrained, num_classes=0, global_pool="")
        self.out_channels = self.backbone.num_features

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.backbone.forward_features(x)


def _feature_grid(extractor: FeatureExtractor, img_size: int) -> tuple[int, int]:
    with torch.no_grad():
        was_training = extractor.training
        extractor.eval()
        h, w = extractor(torch.zeros(1, 3, img_size, img_size)).shape[-2:]
        extractor.train(was_training)
    return int(h), int(w)


class CnnViT(nn.Module):
    """H1: CNN → proyección 1×1 → tokens + posición aprendida + [CLS] → encoder Transformer → clasificador."""

    def __init__(self, num_classes: int, img_size: int = 224, pretrained: bool = False,
                 backbone: str = "efficientnet_b0", d_model: int = 256, depth: int = 2, heads: int = 8,
                 mlp_ratio: float = 2.0, dropout: float = 0.1):
        super().__init__()
        self.features = FeatureExtractor(backbone, pretrained)
        h, w = _feature_grid(self.features, img_size)
        self.proj = nn.Conv2d(self.features.out_channels, d_model, kernel_size=1)
        self.cls_token = nn.Parameter(torch.zeros(1, 1, d_model))
        self.pos_embed = nn.Parameter(torch.zeros(1, 1 + h * w, d_model))
        nn.init.trunc_normal_(self.pos_embed, std=0.02)
        nn.init.trunc_normal_(self.cls_token, std=0.02)
        layer = nn.TransformerEncoderLayer(d_model, heads, int(d_model * mlp_ratio), dropout, batch_first=True,
                                           norm_first=True, activation="gelu")
        self.encoder = nn.TransformerEncoder(layer, depth, enable_nested_tensor=False)
        self.norm = nn.LayerNorm(d_model)
        self.head = nn.Sequential(nn.Dropout(dropout), nn.Linear(d_model, num_classes))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        tokens = self.proj(self.features(x)).flatten(2).transpose(1, 2)  # (B, N, D)
        cls = self.cls_token.expand(tokens.shape[0], -1, -1)
        z = torch.cat([cls, tokens], dim=1)
        if z.shape[1] != self.pos_embed.shape[1]:
            raise ValueError("El tamaño de entrada no coincide con el usado al construir el modelo (img_size).")
        z = self.encoder(z + self.pos_embed)
        return self.head(self.norm(z[:, 0]))


class EffNetAttBiLSTM(nn.Module):
    """H2 (D-06): EfficientNet → parches en orden raster → BiLSTM → atención aditiva → clasificador.

    `last_attention` guarda los pesos de atención por parche de la última pasada (explicabilidad fuera de línea).
    """

    def __init__(self, num_classes: int, img_size: int = 224, pretrained: bool = False,
                 backbone: str = "efficientnet_b0", d_model: int = 256, hidden: int = 128, lstm_layers: int = 1,
                 dropout: float = 0.2):
        super().__init__()
        self.features = FeatureExtractor(backbone, pretrained)
        self.grid = _feature_grid(self.features, img_size)
        self.proj = nn.Conv2d(self.features.out_channels, d_model, kernel_size=1)
        self.lstm = nn.LSTM(d_model, hidden, num_layers=lstm_layers, batch_first=True, bidirectional=True,
                            dropout=dropout if lstm_layers > 1 else 0.0)
        self.att_w = nn.Linear(2 * hidden, hidden)
        self.att_v = nn.Linear(hidden, 1, bias=False)
        self.head = nn.Sequential(nn.Dropout(dropout), nn.Linear(2 * hidden, num_classes))
        self.last_attention: torch.Tensor | None = None

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        seq = self.proj(self.features(x)).flatten(2).transpose(1, 2)  # (B, N, D)
        out, _ = self.lstm(seq)                                       # (B, N, 2H)
        scores = self.att_v(torch.tanh(self.att_w(out))).squeeze(-1)   # (B, N)
        alpha = torch.softmax(scores, dim=1)
        self.last_attention = alpha.detach()
        pooled = (alpha.unsqueeze(-1) * out).sum(dim=1)
        return self.head(pooled)


def build_model(arch: str, num_classes: int, *, img_size: int | None = None, pretrained: bool = False,
                **hparams) -> nn.Module:
    """Construye la arquitectura `arch`. `pretrained=True` descarga pesos ImageNet de timm (Hugging Face Hub)."""
    if arch not in SPECS:
        raise ValueError(f"Arquitectura desconocida: {arch}. Opciones: {', '.join(ARCHITECTURES)}")
    size = img_size or SPECS[arch].default_img_size
    drop = float(hparams.pop("drop_rate", 0.0))
    if arch in TIMM_MODELS:
        if hparams:
            raise ValueError(f"Hiperparámetros no admitidos por {arch}: {sorted(hparams)}")
        overlay = {}
        if pretrained and arch in PRETRAINED_REVISIONS:
            overlay = {"pretrained_cfg_overlay": {
                "hf_hub_id": f"timm/{TIMM_MODELS[arch]}@{PRETRAINED_REVISIONS[arch]}"}}
        return timm.create_model(TIMM_MODELS[arch], pretrained=pretrained, num_classes=num_classes,
                                 drop_rate=drop, **overlay)
    if arch == "cnn_vit":
        return CnnViT(num_classes, size, pretrained, dropout=drop or 0.1, **hparams)
    return EffNetAttBiLSTM(num_classes, size, pretrained, dropout=drop or 0.2, **hparams)


def gradcam_target(model: nn.Module, arch: str) -> nn.Module:
    """Capa cuya salida (mapa de características espacial) usa Grad-CAM en cada arquitectura."""
    if arch == "resnet50":
        return model.layer4
    if arch in ("efficientnet_b3", "efficientnetv2_b0"):
        return model.conv_head
    if arch == "mobilenetv4_conv_medium":
        return model.blocks[-1]  # Antes del pooling: conv_head ya produce 1×1 en MobileNetV4.
    if arch == "efficientvit_b1":
        return model.stages[-1]
    if arch == "convnext_tiny":
        return model.stages[-1]
    if arch in ("cnn_vit", "effnet_att_bilstm"):
        return model.features
    raise ValueError(f"Arquitectura desconocida: {arch}")
