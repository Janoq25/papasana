"""Figuras científicas del artículo derivadas de los resultados congelados."""
import json
import shutil
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import numpy as np

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[1]
source = ROOT / 'ml/data/comparacion-cuatro'
r = json.loads((source / 'results.json').read_text(encoding='utf-8'))
a = json.loads((BASE / 'analisis_derivado.json').read_text(encoding='utf-8'))
report = json.loads((ROOT / 'backend/app/data/training_reports/papasana-cuatro-gpu-20261118.json').read_text(encoding='utf-8'))
byarch = {row['architecture']: row for row in a['models']}
models = report['models']
labels = ['ResNet50', 'EfficientNetV2\nB0', 'MobileNetV4\nConv Medium', 'EfficientViT\nB1']
short = ['ResNet50', 'EffNetV2-B0', 'MobileNetV4-M', 'EfficientViT-B1']
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':8.5,'axes.labelsize':9,'axes.titlesize':10,
                     'legend.fontsize':8,'xtick.labelsize':8,'ytick.labelsize':8,'savefig.dpi':600,
                     'axes.spines.top':False,'axes.spines.right':False})
figures = BASE / 'figures'
figures.mkdir(exist_ok=True)
# La figura metodológica compacta se genera con methodology_figure.py.
colors = ['#176a72','#a34d27','#7051a2','#526b24']

fig,ax=plt.subplots(figsize=(6.3,3.4))
for i,m in enumerate(models):
 h=m['history']['val_macro_f1_epoch']
 ax.plot([p['step'] for p in h],[p['value'] for p in h],label=short[i],color=colors[i],
         linestyle=['-','--',':','-.'][i],marker=['o','s','^','D'][i],markersize=3,linewidth=1.4)
 ax.scatter(m['best_epoch'],m['metrics']['val_macro_f1'],s=70,facecolors='none',edgecolors=colors[i],linewidth=1)
ax.set(xlabel='Época',ylabel='F1 macro interno de tres clases',ylim=(.60,1.03),xlim=(.5,15.5),xticks=[1,3,5,7,9,11,13,15])
ax.yaxis.set_major_formatter(FuncFormatter(lambda v,_: f'{v:.2f}'.replace('.',',')))
ax.grid(axis='y',color='#dfe4e0',linewidth=.6)
ax.legend(loc='lower right',ncol=2,frameon=False)
fig.tight_layout(pad=1.2)
fig.savefig(figures/'figura2_aprendizaje_600dpi.png',dpi=600)
plt.close(fig)

fig,ax=plt.subplots(figsize=(6.3,3.5))
x=np.arange(4)
inside=np.array([byarch[m['architecture']]['val_f1_disease_only'] for m in models])
outside=np.array([byarch[m['architecture']]['external_f1_two'] for m in models])
ci=np.array([byarch[m['architecture']]['external_cluster_bootstrap_f1_ci95'] for m in models])
ax.bar(x-.18,inside,.34,label='Interno condicionado a enfermedad',color='#176a72',edgecolor='white')
ax.bar(x+.18,outside,.34,label='PlantDoc con IC descriptivo del 95 %',color='#bf763c',hatch='//',edgecolor='#5c3b21',linewidth=.4,
       yerr=[outside-ci[:,0],ci[:,1]-outside],capsize=3,error_kw={'linewidth':1,'capthick':1})
for offset,values in [(-.18,inside),(.18,outside)]:
 for i,v in enumerate(values):
  yy = v+.025 if offset<0 else ci[i,1]+.025
  ax.text(x[i]+offset,yy,f'{v:.4f}'.replace('.',','),ha='center',fontsize=8)
ax.set(ylabel='F1 macro de las dos clases de enfermedad',xticks=x,xticklabels=labels,ylim=(0,1.15),yticks=np.arange(0,1.01,.2))
ax.yaxis.set_major_formatter(FuncFormatter(lambda v,_: f'{v:.1f}'.replace('.',',')))
ax.grid(axis='y',color='#dfe4e0',linewidth=.5);ax.set_axisbelow(True)
ax.legend(loc='upper center',bbox_to_anchor=(.5,1.18),frameon=False,ncol=1)
fig.tight_layout(pad=1.0)
fig.savefig(figures/'figura3_transferencia_600dpi.png',dpi=600)
plt.close(fig)

fig,axes=plt.subplots(2,2,figsize=(6.3,5.6))
for i,(ax,m) in enumerate(zip(axes.flat,models,strict=True)):
 cm=np.array(m['evaluation']['external_plantdoc_papa']['confusion_matrix'])
 ax.imshow(cm,cmap='Blues',vmin=0,vmax=82,interpolation='none')
 for y in range(3):
  for z in range(3):
   ax.text(z,y,str(cm[y,z]),ha='center',va='center',color='white' if cm[y,z]>45 else '#182c38',fontsize=11)
 ax.set_title(short[i],pad=7)
 ax.set_xticks(range(3),['Sano','TT','Otra']);ax.set_yticks(range(3),['Sano','TT','Otra'])
 ax.set_xlabel('Predicción');ax.set_ylabel('Referencia')
 ax.set_xticks(np.arange(-.5,3),minor=True);ax.set_yticks(np.arange(-.5,3),minor=True)
 ax.grid(which='minor',color='white',linewidth=2);ax.tick_params(which='minor',bottom=False,left=False)
 for spine in ax.spines.values():spine.set_visible(False)
fig.tight_layout(pad=1.1,h_pad=1.4,w_pad=1.4)
fig.savefig(figures/'figura4_matrices_600dpi.png',dpi=600)
plt.close(fig)

fig,ax=plt.subplots(figsize=(6.3,3.4))
before=np.array([m['evaluation']['external_plantdoc_papa']['calibration']['before']['ece'] for m in models])
after=np.array([m['evaluation']['external_plantdoc_papa']['calibration']['after']['ece'] for m in models])
ax.bar(x-.18,before,.34,color='#176a72',label='Antes de calibrar')
ax.bar(x+.18,after,.34,color='#bf763c',edgecolor='#5c3b21',hatch='//',linewidth=.4,label='Después de calibrar')
for offset,values in [(-.18,before),(.18,after)]:
 for i,v in enumerate(values):ax.text(i+offset,v+.012,f'{v:.3f}'.replace('.',','),ha='center',fontsize=8)
ax.set(xticks=x,xticklabels=labels,ylim=(0,.56),ylabel='Error de calibración esperado en PlantDoc')
ax.yaxis.set_major_formatter(FuncFormatter(lambda v,_: f'{v:.1f}'.replace('.',',')))
ax.grid(axis='y',color='#dfe4e0',linewidth=.5);ax.set_axisbelow(True)
ax.legend(loc='upper center',bbox_to_anchor=(.5,1.15),ncol=2,frameon=False)
fig.tight_layout(pad=1.0)
fig.savefig(figures/'figura5_calibracion_600dpi.png',dpi=600)
plt.close(fig)
print('Cinco figuras de 600 DPI preparadas en',figures)
