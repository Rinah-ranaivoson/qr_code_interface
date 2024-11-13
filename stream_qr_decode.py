import cv2
import urllib.request
import numpy as np
from pyzbar.pyzbar import decode
from datetime import datetime
import json
import os
import tkinter as tk
from tkinter import Scrollbar, Listbox
from PIL import Image, ImageTk, ImageDraw
import threading
import time

# Remplacer l'URL par l'URL de votre flux vidéo ESP32Cam
url = 'http://192.168.137.77/cam-hi.jpg'
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
            {"name": "jack", "code": "XTRUTSMR8I", "poste": "bave"},
            {"name": "jane", "code": "NXYWHPF6G6", "poste": "dev"}
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
def display_image_in_circle(image_path, size=(100, 100)):
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
            image_label.image = img_tk  # Garder une référence à l'image pour éviter qu'elle ne soit collectée par le garbage collector
        else:
            # Si l'utilisateur n'est pas trouvé, afficher un message générique
            name_label.config(text="Nom: Inconnu")
            poste_label.config(text="Fonction: Inconnue")
            image_label.config(image='')  # Vider l'image si l'utilisateur n'est pas trouvé
    except Exception as e:
        print(f"Error selecting log: {e}")

# Fonction pour créer la fenêtre Tkinter et afficher les logs existants
def create_log_window():
    global listbox  # Pour accéder à listbox depuis n'importe où dans le code
    root = tk.Tk()  # Créer la fenêtre Tkinter
    root.title("QR Code Detection Logs")

    # Créer une zone de texte pour afficher les logs
    scrollbar = Scrollbar(root)
    listbox = Listbox(root, width=80, height=20, yscrollcommand=scrollbar.set)
    listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    scrollbar.config(command=listbox.yview)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # Créer des Labels pour afficher le nom et la fonction de l'utilisateur
    name_label = tk.Label(root, text="Nom de l'utilisateur:")
    name_label.pack(padx=10, pady=5)
    name_label.config(text="Nom: Non sélectionné")

    poste_label = tk.Label(root, text="Fonction de l'utilisateur:")
    poste_label.pack(padx=10, pady=5)
    poste_label.config(text="Fonction: Non sélectionnée")

    # Créer un label pour afficher l'image de l'utilisateur dans un cadre rond
    image_label = tk.Label(root)
    image_label.pack(padx=10, pady=5)

    # Charger les logs existants depuis le fichier JSON et les afficher
    detections = load_detections()  # Charger les anciennes détections
    for detection in detections:
        access_status = detection.get('access_status', 'inconnu')  # Valeur par défaut si 'access_status' n'existe pas
        qr_code = detection['qr_code']

        # Charger les informations de l'utilisateur à partir du QR code
        users = load_users()
        if qr_code in users:
            user_info = users[qr_code]
            log_message = f"QR Code detected: {qr_code} ({user_info['name']}, {user_info['poste']}) on camera {detection['camera_id']} at {detection['timestamp']} - Accès {access_status}"
        else:
            log_message = f"QR Code detected: {qr_code} on camera {detection['camera_id']} at {detection['timestamp']} - Accès {access_status}"

        update_log_display(log_message, listbox)

    # Charger les utilisateurs à partir du fichier JSON
    users = load_users()

    # Lier l'événement de clic dans la Listbox pour afficher les infos utilisateur
    listbox.bind("<ButtonRelease-1>", lambda event: on_log_select(event, listbox, users, name_label, poste_label, image_label))

    # Lancer le thread de détection du QR code
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
