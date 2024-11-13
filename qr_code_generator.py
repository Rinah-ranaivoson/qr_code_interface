import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image
import qrcode
import json
import string
import random

# Fonction pour écrire dans le fichier JSON
def write_to_json(name, code, poste, file_name='users.json'):
    data = {
        'name': name,
        'code': code,
        'poste': poste
    }

    try:
        with open(file_name, 'r') as file:
            data_list = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        data_list = []

    data_list.append(data)

    with open(file_name, 'w') as file:
        json.dump(data_list, file, indent=4)

    print(f"Enregistrement ajouté dans {file_name}: {data}")

# Fonction pour générer un code aléatoire
def generate_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))

# Fonction pour rogner l'image et la sauvegarder
def select_and_save_image(file_path, name):
    try:
        # Ouvrir l'image avec Pillow
        img = Image.open(file_path)
        
        # Déterminer la taille du carré (en fonction du plus petit côté)
        width, height = img.size
        min_side = min(width, height)
        
        # Calculer les coordonnées pour rogner l'image au centre
        left = (width - min_side) / 2
        top = (height - min_side) / 2
        right = (width + min_side) / 2
        bottom = (height + min_side) / 2
        
        # Rognage de l'image pour la rendre carrée
        img_cropped = img.crop((left, top, right, bottom))
        
        # Créer un nom pour la nouvelle image basé sur le nom de l'utilisateur
        save_path = f"pdp/{name}.png"
        
        # Sauvegarder l'image rognée en PNG avec le nom personnalisé
        img_cropped.save(save_path, format="PNG")
        print(f"Image sauvegardée sous : {save_path}")
    
    except Exception as e:
        print(f"Erreur lors de la manipulation de l'image : {e}")

# Fonction pour générer et sauvegarder le QR code
def generate_qr_code(code, name):
    qr = qrcode.QRCode(
        version=2,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(code)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    img.save(f"qrcode_png/{name}.png")
    print(f"QR Code sauvegardé sous : qrcode_png/{name}.png")

# Fonction appelée lors du clic sur "Submit"
def on_submit():
    name = name_entry.get()
    poste = poste_entry.get()
    file_path = image_path.get()

    if not name or not poste or not file_path:
        messagebox.showerror("Erreur", "Tous les champs doivent être remplis!")
        return

    # Générer un code aléatoire
    code = generate_code()

    # Sauvegarder les données dans le fichier JSON
    write_to_json(name, code, poste)

    # Générer et sauvegarder le QR code
    generate_qr_code(code, name)

    # Sauvegarder et rogner l'image
    select_and_save_image(file_path, name)

    # Afficher un message de confirmation
    messagebox.showinfo("Succès", "Les données ont été sauvegardées avec succès!")

    # Réinitialiser les champs
    name_entry.delete(0, tk.END)
    poste_entry.delete(0, tk.END)
    image_path.set("")

# Fonction pour ouvrir le sélecteur de fichier d'image
def select_image():
    file_path = filedialog.askopenfilename(
        title="Choisir une image",
        filetypes=[("Image files", "*.png;*.jpeg;*.jpg;*.bmp;*.gif")]
    )
    
    if file_path:
        image_path.set(file_path)

# Création de la fenêtre principale
root = tk.Tk()
root.title("Formulaire d'enregistrement")

# Créer les éléments de l'interface
tk.Label(root, text="Nom :").grid(row=0, column=0, padx=10, pady=10)
name_entry = tk.Entry(root)
name_entry.grid(row=0, column=1, padx=10, pady=10)

tk.Label(root, text="Poste :").grid(row=1, column=0, padx=10, pady=10)
poste_entry = tk.Entry(root)
poste_entry.grid(row=1, column=1, padx=10, pady=10)

tk.Label(root, text="Sélectionner une photo :").grid(row=2, column=0, padx=10, pady=10)
image_path = tk.StringVar()
image_button = tk.Button(root, text="Choisir une image", command=select_image)
image_button.grid(row=2, column=1, padx=10, pady=10)

submit_button = tk.Button(root, text="Soumettre", command=on_submit)
submit_button.grid(row=3, column=0, columnspan=2, pady=20)

# Démarrer l'application Tkinter
root.mainloop()
