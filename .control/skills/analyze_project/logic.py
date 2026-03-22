import os
from pathlib import Path

def run_skill():
    output_path = Path(".control/outputs/project_inventory.md")
    # Aseguramos que la carpeta de salida existe
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    ignored = {'.git', 'venv', '__pycache__', 'node_modules', '.control'}
    inventory = ["# 📊 Informe de Inteligencia: Inventario del Proyecto\n"]
    
    # 1. Analizar Estructura
    inventory.append("## 📁 Estructura de Carpetas")
    for root, dirs, files in os.walk("."):
        # Filtramos carpetas ignoradas
        dirs[:] = [d for d in dirs if d not in ignored]
        
        # Calculamos nivel para la indentación
        level = root.replace(os.sep, '/').count('/')
        if level > 3: continue  # No profundizamos demasiado para no saturar
        
        indent = '  ' * level
        folder_name = os.path.basename(root) or "Raíz"
        inventory.append(f"{indent}- {folder_name}/")
        
        sub_indent = '  ' * (level + 1)
        for f in files:
            inventory.append(f"{sub_indent}- {f}")

    # 2. Leer README si existe (un vistazo rápido)
    readme = Path("README.md")
    if readme.exists():
        inventory.append("\n## 📖 Resumen del README")
        try:
            content = readme.read_text(encoding="utf-8").splitlines()
            inventory.append(f"> {content[0] if content else 'Archivo vacío'}")
        except Exception:
            inventory.append("> (No se pudo leer el contenido)")

    output_path.write_text("\n".join(inventory), encoding="utf-8")
    print(f"✅ Inventario generado con éxito en: {output_path}")

if __name__ == "__main__":
    run_skill()