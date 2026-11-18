"""Figura metodológica compacta y reproducible para el manuscrito."""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
BASE=Path(__file__).resolve().parent
fig,ax=plt.subplots(figsize=(6.3,5.4))
ax.set(xlim=(0,1),ylim=(0,1))
ax.axis("off")
ax.set_position([0,0,1,1])
def box(x,y,w,h,text,color="#eef3f4"):
    ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle="round,pad=0.012,rounding_size=0.012",
                               facecolor=color,edgecolor="#49636a",linewidth=.85))
    ax.text(x+w/2,y+h/2,text,ha="center",va="center",fontsize=8.6,color="#182f35",linespacing=1.35)
def arrow(a,b,dashed=False):
    ax.annotate("",xy=b,xytext=a,arrowprops={"arrowstyle":"->","color":"#49636a",
                 "lw":1.1,"linestyle":"--" if dashed else "-"})
box(.06,.855,.88,.115,"Fuentes públicas de imágenes de papa\nPlantVillage 2152  +  PlantDoc 222  =  2374 imágenes")
box(.06,.665,.88,.115,"Control de calidad y agrupación\nSHA-256 · dHash de 64 bits con distancia ≤ 4 · identificador de hoja\n5 duplicados exactos retirados y 9 etiquetas en conflicto excluidas")
arrow((.5,.855),(.5,.785))
box(.04,.435,.43,.15,"PlantVillage 2152 imágenes\n538 hojas · 537 grupos finales\n5 pliegues por grupos y clases\nPliegue 1\n1724 entrenamiento · 428 validación")
box(.54,.435,.42,.15,"PlantDoc 208 imágenes\n206 grupos · 98 tizón y 110 otra\nSin referencias sanas\nEvaluación externa descriptiva", "#f7efe7")
arrow((.27,.665),(.27,.59))
arrow((.75,.665),(.75,.59))
box(.04,.205,.43,.15,"Entrenar cuatro arquitecturas\n224 px · AdamW · máximo 16 épocas\nGPU local · FP16 o BF16\nSelección y temperatura con validación")
arrow((.255,.435),(.255,.36))
box(.54,.205,.42,.15,"Modelos y temperatura congelados\nSin ajustes con PlantDoc\nClasificación y calibración externas\nIC por 5000 remuestreos de grupos", "#f7efe7")
arrow((.75,.435),(.75,.36),True)
arrow((.47,.28),(.535,.28))
box(.06,.025,.88,.10,"Verificar pesos y matrices · NLL estable en log-espacio\nPublicar tablas y figuras a 600 dpi en PapaSana y en el artículo")
arrow((.255,.205),(.255,.13))
arrow((.75,.205),(.75,.13))
fig.savefig(BASE/"figures/figura1_metodologia_600dpi.png",dpi=600,bbox_inches="tight",pad_inches=.08,facecolor="white")
plt.close(fig)
print("Figura metodológica actualizada")

