import cv2
import urllib.request
import numpy as np
from pyzbar.pyzbar import decode
from datetime import datetime
import json
import os
import customtkinter as ctk
import tkinter as tk
from tkinter import font
from tkinter import Scrollbar, Listbox, filedialog, messagebox
from PIL import Image, ImageTk, ImageDraw
import threading
import time
import qrcode
import string
import random


# Valeurs par défaut
default_config = {
    "esp32_ip": "192.168.1.100",  
    "cam_resolution": "mid"
}

# Chemin du fichier de configuration
config_file_path = 'config.json'

# Tenter de lire le fichier de configuration, sinon le créer
if not os.path.exists(config_file_path):
    # Si le fichier n'existe pas, le créer avec les valeurs par défaut
    with open(config_file_path, 'w') as config_file:
        json.dump(default_config, config_file, indent=4)
    print("Fichier de configuration créé avec les valeurs par défaut.")
    config = default_config  # Utiliser les valeurs par défaut si le fichier n'existe pas
else:
    # Lire le fichier de configuration existant
    with open(config_file_path) as config_file:
        config = json.load(config_file)

# Extraire les données du fichier de configuration
esp32_ip = config['esp32_ip']
cam_resolution = config['cam_resolution']
url = f"http://{esp32_ip}/cam-{cam_resolution}.jpg"
camera_id = "a1"

# Fichiers JSON pour stocker les détections et les utilisateurs
detections_file = "detections.json"
users_file = "users.json"
images_folder = "pdp"  # Dossier contenant les images des utilisateurs

# Variable pour stocker le dernier QR code détecté
last_detected_code = None

# Si le fichier des détections n'existe pas ou est vide, initialisez-le avec une liste vide
if not os.path.exists(detections_file):
    with open(detections_file, 'w') as f:
        json.dump([], f)

# Si le fichier des utilisateurs n'existe pas, vous pouvez créer un exemple
if not os.path.exists(users_file):
    with open(users_file, 'w') as f:
        json.dump([
            {"name": "jack", "code": "XTRUMR8I", "poste": "bave"},
            {"name": "jane", "code": "NXYWF6G6", "poste": "dev"}
        ], f)

# Fonction pour charger les détections du fichier JSON
def load_detections():
    try:
        with open(detections_file, 'r') as f:
            detections = json.load(f)
            if detections is None:
                return []
            return detections
    except (json.JSONDecodeError, ValueError):
        # Si le fichier est vide ou corrompu, retourner une liste vide
        return []

# Fonction pour sauvegarder les détections dans le fichier JSON
def save_detections(detections):
    with open(detections_file, 'w') as f:
        json.dump(detections, f, indent=4)

# Fonction pour charger les utilisateurs à partir du fichier JSON
def load_users():
    try:
        with open(users_file, 'r') as f:
            users = json.load(f)
            return {user["code"]: {"name": user["name"], "poste": user["poste"], "image": user["name"].lower() + ".png"} for user in users}
    except (json.JSONDecodeError, ValueError):
        # Si le fichier est vide ou corrompu, retourner une liste vide
        return {}

# Fonction pour afficher une image dans un cadre rond
def display_image_in_circle(image_path, size=(150, 150)):
    # Ouvrir l'image avec PIL
    img = Image.open(image_path)
    
    # Redimensionner l'image à la taille souhaitée
    img = img.resize(size, Image.ANTIALIAS)
    
    # Créer un masque circulaire
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, size[0], size[1]), fill=255)
    
    # Appliquer le masque circulaire à l'image
    img.putalpha(mask)
    
    # Convertir l'image PIL en format Tkinter compatible
    img_tk = ImageTk.PhotoImage(img)
    
    return img_tk

# Fonction pour mettre à jour la fenêtre Tkinter avec les nouveaux logs
def update_log_display(log_message, listbox):
    listbox.insert(tk.END, log_message)
    listbox.yview(tk.END)  # Faites défiler automatiquement vers le bas

# Fonction pour afficher les informations de l'utilisateur lorsqu'on clique sur un log
def on_log_select(event, listbox, users, name_label, poste_label, image_label):
    try:
        # Récupérer l'index de l'élément sélectionné
        selection = listbox.curselection()
        if not selection:
            return
        selected_log = listbox.get(selection[0])

        # Extraire le code QR du log sélectionné
        code_value = selected_log.split(' ')[3]  # Le code QR est toujours à la 4ème position dans le log
        
        # Vérifier si le code QR existe dans les utilisateurs
        if code_value in users:
            user_info = users[code_value]
            # Mettre à jour les labels avec le nom et le poste
            name_label.config(text=f"Nom: {user_info['name']}")
            poste_label.config(text=f"Fonction: {user_info['poste']}")
            
            # Afficher l'image dans le label
            image_path = os.path.join(images_folder, user_info["image"])
            img_tk = display_image_in_circle(image_path)
            image_label.config(image=img_tk)
            image_label.config(bg= 'grey14')  # Exemple : fond blanc
            image_label.image = img_tk  # Garder une référence à l'image pour éviter qu'elle ne soit collectée par le garbage collector
        else:
            # Si l'utilisateur n'est pas trouvé, afficher un message générique
            name_label.config(text="Nom: Inconnu")
            poste_label.config(text="Fonction: Inconnue")
            image_label.config(image='')  # Vider l'image si l'utilisateur n'est pas trouvé
    except Exception as e:
        print(f"Error selecting log: {e}")


# Fonction pour gérer la fenêtre de gestion des utilisateurs après identification
def user_manager_window():

    # Fonction pour écrire dans le fichier JSON
    def write_to_json(name, code, poste, file_name='users.json'):
        data = {
            'name': name,
            'code': code,
            'poste': poste
        }

        # Vérifier si le répertoire contenant le fichier existe
        import os
        dir_name = os.path.dirname(file_name)
        if dir_name and not os.path.exists(dir_name):
            os.makedirs(dir_name)
            print(f"Répertoire créé : {dir_name}")

        try:
            # Charger les données existantes ou créer une liste vide
            with open(file_name, 'r') as file:
                data_list = json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            data_list = []

        # Ajouter les nouvelles données
        data_list.append(data)

        # Écrire les données dans le fichier JSON
        with open(file_name, 'w') as file:
            json.dump(data_list, file, indent=4)

        print(f"Enregistrement ajouté dans {file_name}: {data}")


    # Fonction pour générer un code aléatoire
    def generate_code():
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))

    # Fonction pour rogner l'image et la sauvegarder
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
            
            # Vérifier et créer le dossier `pdp/` si nécessaire
            import os
            save_dir = "pdp"
            if not os.path.exists(save_dir):
                os.makedirs(save_dir)
                print(f"Dossier créé : {save_dir}")
            
            # Créer un nom pour la nouvelle image basé sur le nom de l'utilisateur
            save_path = f"{save_dir}/{name}.png"
            
            # Sauvegarder l'image rognée en PNG avec le nom personnalisé
            img_cropped.save(save_path, format="PNG")
            print(f"Image sauvegardée sous : {save_path}")
        
        except Exception as e:
            print(f"Erreur lors de la manipulation de l'image : {e}")


    # Fonction pour générer et sauvegarder le QR code
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
        
        # Vérifier et créer le dossier `qrcode_png/` si nécessaire
        import os
        save_dir = "qrcode_png"
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
            print(f"Dossier créé : {save_dir}")

        # Sauvegarder le QR code
        save_path = f"{save_dir}/{name}.png"
        img.save(save_path)
        print(f"QR Code sauvegardé sous : {save_path}")


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

    manager_root = ctk.CTkToplevel() # Créer une nouvelle fenêtre
    manager_root.title("Gestionnaire d'utilisateur")
    manager_root.attributes('-topmost', 1)
    
    # Ajouter un label de bienvenue
    welcome_label = ctk.CTkLabel(manager_root, text="Bienvenue sur le gestionnaire d'utilisateur", font=("Arial", 14))
    welcome_label.grid(row=0, column=0, columnspan=2, pady=10)
    
    # Ajouter les champs d'entrée
    ctk.CTkLabel(manager_root, text="Nom :").grid(row=1, column=0, padx=10, pady=10)
    name_entry = ctk.CTkEntry(manager_root)
    name_entry.grid(row=1, column=1, padx=10, pady=10)

    ctk.CTkLabel(manager_root, text="Poste :").grid(row=2, column=0, padx=10, pady=10)
    poste_entry = ctk.CTkEntry(manager_root)
    poste_entry.grid(row=2, column=1, padx=10, pady=10)

    ctk.CTkLabel(manager_root, text="Sélectionner une photo :").grid(row=3, column=0, padx=10, pady=10)
    image_path = tk.StringVar()
    image_button = ctk.CTkButton(manager_root, text="Choisir une image", command=select_image)
    image_button.grid(row=3, column=1, padx=10, pady=10)

    submit_button = ctk.CTkButton(manager_root, text="Soumettre", command=on_submit)
    submit_button.grid(row=4, column=0, columnspan=2, pady=20)
    
    # Ajouter un bouton pour quitter la fenêtre
    exit_button = ctk.CTkButton(manager_root, text="Sortir", command=manager_root.destroy, font=("Arial", 12))
    exit_button.grid(row=5, column=0, columnspan=2, pady=20)


# Fonction pour gérer l'authentification avec mot de passe
def authenticate_user():
    def verify_password():
        entered_password = password_entry.get()
        if entered_password == "po":
            auth_window.destroy()  # Fermer la fenêtre d'authentification
            user_manager_window()  # Ouvrir la fenêtre de gestion des utilisateurs
        else:
            error_label.configure(text="Mot de passe incorrect, réessayez.", text_color="red")

    # Créer une fenêtre pour l'authentification
    auth_window = ctk.CTkToplevel()
    auth_window.attributes('-topmost', 1)
    auth_window.title("Authentification")
    auth_window.geometry("300x200")

    # Ajouter un label pour la saisie du mot de passe
    password_label = ctk.CTkLabel(auth_window, text="Entrez le mot de passe:", font=("Ubuntu", 14))
    password_label.pack(pady=10, padx=10)

    # Ajouter une entrée pour le mot de passe
    password_entry = ctk.CTkEntry(auth_window, show="*", font=("Arial", 12))
    password_entry.pack(pady=10, padx=10)

    # Ajouter un bouton pour valider le mot de passe
    submit_button = ctk.CTkButton(auth_window, text="Valider", command=verify_password, font=("Arial", 12))
    submit_button.pack(pady=10)

    # Ajouter un label pour afficher les erreurs
    global error_label
    error_label = ctk.CTkLabel(auth_window, text="", font=("Arial", 10))
    error_label.pack(pady=5)

# Ajouter un bouton "Ajouter utilisateur" à la fenêtre principale
def create_log_window():
    global listbox
    root = ctk.CTk()  # Crée la fenêtre principale
    root.title("QR Code Detection Logs")
    custom_font = font.Font(family="Ubuntu", size=14)  
    custom_font2 = font.Font(family="Ubuntu", size=18)  

    # Créer une zone de texte pour afficher les logs
    scrollbar = Scrollbar(root)
    listbox = Listbox(root, width=120, height=25, yscrollcommand=scrollbar.set, font= custom_font)
    listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    scrollbar.config(command=listbox.yview)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # Créer des labels pour afficher les détails de l'utilisateur
    name_label = tk.Label(root, text="Nom: Non sélectionné", font=custom_font2, fg='white', bg= root.cget("bg"))
    name_label.pack(padx=10, pady=5)
    poste_label = tk.Label(root, text="Fonction: Non sélectionnée", font= custom_font2, fg='white', bg= root.cget("bg"))
    poste_label.pack(padx=10, pady=5)

    image_label = tk.Label(root)
    image_label.pack(padx=10, pady=5)

    detections = load_detections()
    for detection in detections:
        access_status = detection.get('access_status', 'inconnu')
        qr_code = detection['qr_code']
        users = load_users()

        if qr_code in users:
            user_info = users[qr_code]
            log_message = f"QR Code detected: {qr_code} ({user_info['name']}, {user_info['poste']}) on camera {detection['camera_id']} at {detection['timestamp']} - Accès {access_status}"
        else:
            log_message = f"QR Code detected: {qr_code} on camera {detection['camera_id']} at {detection['timestamp']} - Accès {access_status}"

        update_log_display(log_message, listbox)

    users = load_users()
    listbox.bind("<ButtonRelease-1>", lambda event: on_log_select(event, listbox, users, name_label, poste_label, image_label))

    # Ajouter le bouton "Ajouter utilisateur"
    add_user_button = ctk.CTkButton(root, text="Ajouter utilisateur", text_color="white", command=authenticate_user, font=("Ubuntu", 15))
    add_user_button.pack(side="bottom", pady=20, padx= 40)

    detection_thread = threading.Thread(target=process_frame, args=(root, users, listbox))
    detection_thread.daemon = True
    detection_thread.start()

    root.mainloop()


# Fonction pour traiter les images et détecter les QR codes dans un thread
def process_frame(root, users, listbox):
    global last_detected_code
    while True:
        try:
            # Lire le flux vidéo à partir de l'ESP32Cam
            img_resp = urllib.request.urlopen(url)
            imgnp = np.array(bytearray(img_resp.read()), dtype=np.uint8)

            # Décoder l'image en utilisant OpenCV
            frame = cv2.imdecode(imgnp, -1)

            # Si une image est récupérée avec succès
            if frame is not None:
                # Décoder les QR codes dans l'image
                for d in decode(frame):
                    s = d.data.decode()  # Décoder le contenu du QR code
                    code_value = s

                    # Si le QR code détecté est différent du précédent, afficher et mettre à jour
                    if code_value != last_detected_code:
                        # Obtenir la date et l'heure actuelle
                        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                        # Charger les utilisateurs à partir du fichier JSON
                        users = load_users()

                        # Vérifier si le code QR est valide
                        if code_value in users:
                            # QR code reconnu, afficher carré vert
                            print(f"QR Code detected: {code_value} - Accès accepté")

                            # Ajouter une entrée dans les logs : accès accepté
                            access_status = "accepté"
                            log_message = f"QR Code detected: {code_value} ({users[code_value]['name']}, {users[code_value]['poste']}) on camera {camera_id} at {current_time} - Accès {access_status}"
                        else:
                            # QR code non reconnu, afficher carré rouge
                            print(f"QR Code detected: {code_value} - Accès refusé")

                            # Ajouter une entrée dans les logs : accès refusé
                            access_status = "refusé"
                            log_message = f"QR Code detected: {code_value} on camera {camera_id} at {current_time} - Accès {access_status}"

                        # Créer un dictionnaire avec les informations à ajouter
                        detection_info = {
                            "qr_code": code_value,
                            "camera_id": camera_id,
                            "timestamp": current_time,
                            "access_status": access_status
                        }

                        # Charger les détections actuelles depuis le fichier JSON
                        detections = load_detections()

                        # Ajouter la nouvelle détection à la liste
                        detections.append(detection_info)

                        # Sauvegarder la liste mise à jour dans le fichier JSON
                        save_detections(detections)

                        # Mettre à jour le dernier code détecté
                        last_detected_code = code_value

                        # Utiliser root.after() pour mettre à jour la liste des logs dans l'interface Tkinter
                        root.after(0, update_log_display, log_message, listbox)

        except Exception as e:
            print(f"Error processing frame: {e}")
        time.sleep(1)  # Attendre un peu avant de traiter le prochain frame

# Lancer l'application Tkinter
create_log_window()
