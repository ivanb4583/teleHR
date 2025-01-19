import sys
import requests
import base64
from cryptography.fernet import Fernet
from PyQt5 import QtCore, QtGui, QtWidgets
import mysql.connector
from datetime import datetime

def load_db_config():
    try:
        with open("db1.txt", "r") as file:
            lines = file.readlines()
        return {
            "host": lines[0].strip(),
            "user": lines[1].strip(),
            "password": lines[2].strip(),
            "database": lines[3].strip(),
            "port": int(lines[4].strip())
        }
    except Exception as e:
        print(f"Error loading DB config: {e}")
        sys.exit(1)

class LoginDialog(QtWidgets.QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("HR Panel Login")
        self.setModal(True)
        
        # Зашифрованный URL и ключ
        self.key = b'dLn2L6denNtcaq-Zkwi7FB9F70RaGXNFHfPk1U8PX8A='
        self.encoded_url = b'gAAAAABnjEFRfaFKrmF7FGSc41q8I80P9C0Vy3HKn6L-qqrG01wlG9oBKNj2QOKntRkT_nZlYfO_jSoQiMnKngsDcQWENDjOw1YgVZxqjpguqef3rnVMdcjezDIx3qVAV8wUDcl4kGo6'
        
        layout = QtWidgets.QVBoxLayout(self)
        
        # Поля ввода
        self.login = QtWidgets.QLineEdit()
        self.login.setPlaceholderText("Login")
        layout.addWidget(self.login)
        
        # Контейнер для пароля и кнопки показа
        password_container = QtWidgets.QHBoxLayout()
        
        self.password = QtWidgets.QLineEdit()
        self.password.setPlaceholderText("Password")
        self.password.setEchoMode(QtWidgets.QLineEdit.Password)
        password_container.addWidget(self.password)
        
        # Кнопка показа пароля
        self.toggle_password = QtWidgets.QPushButton("👁")  # Заменяем иконку на эмодзи
        self.toggle_password.setFixedWidth(30)
        self.toggle_password.clicked.connect(self.toggle_password_visibility)
        password_container.addWidget(self.toggle_password)
        
        layout.addLayout(password_container)
        
        # Кнопка входа
        self.login_button = QtWidgets.QPushButton("Вход")
        self.login_button.clicked.connect(self.check_credentials)
        layout.addWidget(self.login_button)
        
        self.error_label = QtWidgets.QLabel("")
        self.error_label.setStyleSheet("color: red")
        layout.addWidget(self.error_label)
        
    def toggle_password_visibility(self):
        if self.password.echoMode() == QtWidgets.QLineEdit.Password:
            self.password.setEchoMode(QtWidgets.QLineEdit.Normal)
            self.toggle_password.setText("✓")
        else:
            self.password.setEchoMode(QtWidgets.QLineEdit.Password)
            self.toggle_password.setText("👁")

    def decrypt_url(self):
        f = Fernet(self.key)
        decrypted_url = f.decrypt(self.encoded_url).decode()
        return decrypted_url

    def check_credentials(self):
        try:
            response = requests.get(self.decrypt_url())
            if response.status_code == 200:
                credentials = response.text.strip().split('\n')
                for cred in credentials:
                    login, password = cred.strip().split(':')
                    if login == self.login.text() and password == self.password.text():
                        self.accept()
                        return
                self.error_label.setText("Неверный логин или пароль")
            else:
                self.error_label.setText("Ошибка проверки учетных данных")
        except Exception as e:
            self.error_label.setText(f"Ошибка: {str(e)}")

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        # Сначала показываем окно логина
        login_dialog = LoginDialog()
        if login_dialog.exec_() != QtWidgets.QDialog.Accepted:
            sys.exit()
            
        self.setWindowTitle("HR Panel")
        self.config = load_db_config()
        
        # Создаем вкладки
        self.tabs = QtWidgets.QTabWidget()
        self.setCentralWidget(self.tabs)
        
        # Вкладка Leads
        self.leads_tab = QtWidgets.QWidget()
        self.setup_leads_tab()
        self.tabs.addTab(self.leads_tab, "Leads")
        
        # Вкладка Reviews
        self.reviews_tab = QtWidgets.QWidget()
        self.setup_reviews_tab()
        self.tabs.addTab(self.reviews_tab, "Reviews")
        
        # Вкладка Approved
        self.approved_tab = QtWidgets.QWidget()
        self.setup_approved_tab()
        self.tabs.addTab(self.approved_tab, "Approved")
        
        self.load_data()
        self.load_reviews()
        self.load_approved()

    def setup_leads_tab(self):
        layout = QtWidgets.QVBoxLayout(self.leads_tab)
        # Переносим существующий код для leads сюда
        self.search_edits = []
        search_layout = QtWidgets.QHBoxLayout()
        search_headers = ["id", "telegram_id", "response_date", "name", "phone_number", "email", "hr"]
        for header in search_headers:
            edit = QtWidgets.QLineEdit()
            edit.setPlaceholderText(f"Поиск {header}...")
            edit.textChanged.connect(self.apply_filters)
            self.search_edits.append(edit)
            search_layout.addWidget(edit)
        layout.addLayout(search_layout)

        self.table = QtWidgets.QTableWidget()
        headers = ["id", "telegram_id", "response_date", "name", "phone_number", "email", "english_level", "modern_pc", "hr"]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setStyleSheet("QTableWidget {background-color: #f0f0f0; gridline-color: #d0d0d0;}")
        self.table.horizontalHeader().setStyleSheet("QHeaderView::section {background-color: #d0d0d0;}")
        layout.addWidget(self.table)

        button_layout = QtWidgets.QHBoxLayout()
        refresh_button = QtWidgets.QPushButton("Refresh")
        refresh_button.clicked.connect(self.load_data)
        button_layout.addWidget(refresh_button)

        delete_button = QtWidgets.QPushButton("Удалить")
        delete_button.clicked.connect(self.delete_record)
        button_layout.addWidget(delete_button)
        layout.addLayout(button_layout)

    def setup_reviews_tab(self):
        layout = QtWidgets.QVBoxLayout(self.reviews_tab)
        
        # Таблица отзывов
        self.reviews_table = QtWidgets.QTableWidget()
        headers = ["date", "name", "review"]
        self.reviews_table.setColumnCount(len(headers))
        self.reviews_table.setHorizontalHeaderLabels(headers)
        self.reviews_table.horizontalHeader().setStretchLastSection(True)
        self.reviews_table.setStyleSheet("QTableWidget {background-color: #f0f0f0; gridline-color: #d0d0d0;}")
        self.reviews_table.horizontalHeader().setStyleSheet("QHeaderView::section {background-color: #d0d0d0;}")
        layout.addWidget(self.reviews_table)

        # Кнопка обновления
        refresh_button = QtWidgets.QPushButton("Refresh Reviews")
        refresh_button.clicked.connect(self.load_reviews)
        layout.addWidget(refresh_button)

    def setup_approved_tab(self):
        layout = QtWidgets.QVBoxLayout(self.approved_tab)
        
        # Верхняя панель с фильтрами
        filter_layout = QtWidgets.QHBoxLayout()
        
        # Фильтр по статусу - обновляем список статусов
        self.status_combo = QtWidgets.QComboBox()
        self.status_combo.addItems(["All", "NEW", "STUDY", "WORK", "LEFT"])
        self.status_combo.currentTextChanged.connect(self.apply_approved_filters)
        filter_layout.addWidget(QtWidgets.QLabel("Status:"))
        filter_layout.addWidget(self.status_combo)
        
        # Фильтр по админу - используем admins.txt вместо admin.txt
        self.admin_combo = QtWidgets.QComboBox()
        self.admin_combo.addItem("All")
        try:
            with open("admins.txt", "r") as file:
                self.admins = [line.strip() for line in file]
                self.admin_combo.addItems(self.admins)
        except Exception as e:
            print(f"Error loading admins list: {e}")
        
        self.admin_combo.currentTextChanged.connect(self.apply_approved_filters)
        filter_layout.addWidget(QtWidgets.QLabel("Admin:"))
        filter_layout.addWidget(self.admin_combo)
        
        # Добавляем поле для поиска по имени
        self.name_search = QtWidgets.QLineEdit()
        self.name_search.setPlaceholderText("Name search...")
        self.name_search.textChanged.connect(self.apply_approved_filters)
        filter_layout.addWidget(QtWidgets.QLabel("Name:"))
        filter_layout.addWidget(self.name_search)
        
        layout.addLayout(filter_layout)
        
        # Таблица
        self.approved_table = QtWidgets.QTableWidget()
        headers = ["Status", "Date", "Name", "Country", "Admin", "Stage", "RejectReason"]
        self.approved_table.setColumnCount(len(headers))
        self.approved_table.setHorizontalHeaderLabels(headers)
        self.approved_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.approved_table)
        
        # Кнопки
        button_layout = QtWidgets.QHBoxLayout()
        
        refresh_button = QtWidgets.QPushButton("Refresh")
        refresh_button.clicked.connect(self.load_approved)
        button_layout.addWidget(refresh_button)
        
        assign_admin_button = QtWidgets.QPushButton("Assign Admin")
        assign_admin_button.clicked.connect(self.assign_admin)
        button_layout.addWidget(assign_admin_button)
        
        add_worker_button = QtWidgets.QPushButton("Add Worker")
        add_worker_button.setStyleSheet("background-color: #d4ffd4;")  # Очень бледно зеленый
        add_worker_button.clicked.connect(self.add_worker)
        button_layout.addWidget(add_worker_button)

        layout.addLayout(button_layout)

    def add_worker(self):
        class AddWorkerDialog(QtWidgets.QDialog):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.setWindowTitle("HR Adding Module")
                self.setMinimumWidth(450)
                self.setup_ui()

            def setup_ui(self):
                layout = QtWidgets.QVBoxLayout(self)

                # Текстовое поле для ввода
                self.label = QtWidgets.QLabel("Enter worker details:")
                layout.addWidget(self.label)

                self.text_input = QtWidgets.QPlainTextEdit()
                self.text_input.setMinimumHeight(200)
                layout.addWidget(self.text_input)

                # Кнопки
                button_layout = QtWidgets.QHBoxLayout()
                
                self.paste_button = QtWidgets.QPushButton("Paste")
                self.paste_button.clicked.connect(self.paste_from_clipboard)
                self.paste_button.setStyleSheet("background-color: #d4ffd4;")
                button_layout.addWidget(self.paste_button)

                self.save_button = QtWidgets.QPushButton("Save")
                self.save_button.clicked.connect(self.save_record)
                self.save_button.setStyleSheet("background-color: #d4d4ff;")
                button_layout.addWidget(self.save_button)

                layout.addLayout(button_layout)

                # Поле для удаления
                self.delete_label = QtWidgets.QLabel("Enter ID to delete:")
                layout.addWidget(self.delete_label)

                self.delete_input = QtWidgets.QLineEdit()
                layout.addWidget(self.delete_input)

                self.delete_button = QtWidgets.QPushButton("Delete")
                self.delete_button.clicked.connect(self.delete_worker)
                self.delete_button.setStyleSheet("background-color: #ffd4d4;")
                layout.addWidget(self.delete_button)

            def parse_input(self, input_text):
                lines = input_text.split('\n')
                data = {}
                for line in lines:
                    if line.startswith("Name:"):
                        data['Name'] = line.split("Name:")[1].strip()
                    elif line.startswith("Phone:"):
                        data['Phone'] = line.split("Phone:")[1].strip()
                    elif line.startswith("Age:"):
                        data['Age'] = line.split("Age:")[1].strip()
                    elif line.startswith("telegram"):
                        data['Telegram'] = line.split("telegram")[1].strip()
                    elif line.startswith("email"):
                        data['Email'] = line.split("email")[1].strip()
                return data

            def save_to_database(self, data):
                try:
                    with open("db3.txt", "r") as file:
                        lines = file.readlines()
                        db3_config = {
                            "host": lines[0].strip(),
                            "user": lines[1].strip(),
                            "password": lines[2].strip(),
                            "database": "TranslatorDB",
                            "port": int(lines[4].strip()),
                        }
                    
                    conn = mysql.connector.connect(**db3_config)
                    cursor = conn.cursor()

                    current_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S.000000')
                    note = f"age: {data.get('Age', '')}\ntelegram: {data.get('Telegram', '')}"
                    query = """
                    INSERT INTO Workers (Name, Note, Email, Date, Status, Source, Country, Number)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    values = (
                        data['Name'],
                        note,
                        data.get('Email', ''),
                        current_date,
                        "NEW",
                        "Facebook",
                        "NG",
                        data.get('Phone', '')
                    )

                    cursor.execute(query, values)
                    conn.commit()
                    inserted_id = cursor.lastrowid

                    cursor.close()
                    conn.close()

                    return inserted_id
                except Exception as e:
                    QtWidgets.QMessageBox.critical(self, "Error", f"Database Error: {str(e)}")
                    return None

            def save_record(self):
                input_text = self.text_input.toPlainText().strip()
                if not input_text:
                    QtWidgets.QMessageBox.warning(self, "Error", "Please enter the required data.")
                    return

                parsed_data = self.parse_input(input_text)
                if 'Name' not in parsed_data or not parsed_data['Name']:
                    QtWidgets.QMessageBox.warning(self, "Error", "Name is required.")
                    return

                record_id = self.save_to_database(parsed_data)
                if record_id:
                    QtWidgets.QMessageBox.information(self, "Success", 
                        f"Record saved successfully with ID: {record_id}")
                    self.text_input.clear()
                    self.parent().load_approved()

            def paste_from_clipboard(self):
                clipboard = QtWidgets.QApplication.clipboard()
                self.text_input.insertPlainText(clipboard.text())

            def delete_worker(self):
                record_id = self.delete_input.text().strip()
                if not record_id:
                    QtWidgets.QMessageBox.warning(self, "Error", "Please enter a valid ID.")
                    return

                try:
                    with open("db3.txt", "r") as file:
                        lines = file.readlines()
                        db3_config = {
                            "host": lines[0].strip(),
                            "user": lines[1].strip(),
                            "password": lines[2].strip(),
                            "database": "TranslatorDB",
                            "port": int(lines[4].strip()),
                        }
                    
                    conn = mysql.connector.connect(**db3_config)
                    cursor = conn.cursor()

                    cursor.execute("DELETE FROM Workers WHERE id = %s", (record_id,))
                    conn.commit()

                    if cursor.rowcount > 0:
                        QtWidgets.QMessageBox.information(self, "Success", 
                            f"Record with ID {record_id} deleted successfully.")
                        self.delete_input.clear()
                        self.parent().load_approved()
                    else:
                        QtWidgets.QMessageBox.warning(self, "Error", 
                            f"No record found with ID {record_id}.")

                    cursor.close()
                    conn.close()
                except Exception as e:
                    QtWidgets.QMessageBox.critical(self, "Error", f"Database Error: {str(e)}")

        dialog = AddWorkerDialog(self)
        dialog.exec_()

    def load_reviews(self):
        try:
            # Подключаемся к базе данных из db2.txt
            with open("db2.txt", "r") as file:
                lines = file.readlines()
                db2_config = {
                    "host": lines[0].strip(),
                    "user": lines[1].strip(),
                    "password": lines[2].strip(),
                    "database": lines[3].strip(),
                    "port": int(lines[4].strip()),
                }
            
            conn = mysql.connector.connect(**db2_config)
            cursor = conn.cursor()
            cursor.execute("SELECT timestamp, name, review FROM reviews ORDER BY timestamp DESC")
            rows = cursor.fetchall()
            conn.close()

            self.reviews_table.setRowCount(len(rows))
            for row_index, row_data in enumerate(rows):
                for col_index, value in enumerate(row_data):
                    if col_index == 0 and value:  # Дата
                        if isinstance(value, datetime):
                            value = value.strftime("%d/%m/%y %H:%M")
                        else:
                            value = datetime.strptime(value, "%Y-%m-%d %H:%M:%S").strftime("%d/%m/%y %H:%M")
                    item = QtWidgets.QTableWidgetItem(str(value) if value else "")
                    self.reviews_table.setItem(row_index, col_index, item)

            # Устанавливаем ширину столбцов
            self.reviews_table.setColumnWidth(0, 100)  # date
            self.reviews_table.setColumnWidth(1, 150)  # name
            self.reviews_table.setColumnWidth(2, 400)  # review

            print("Reviews loaded successfully")
        except Exception as e:
            print(f"Error loading reviews: {e}")

    def load_data(self):
        try:
            conn = mysql.connector.connect(**self.config)
            cursor = conn.cursor()
            
            # Получаем списки дублирующихся telegram_id и phone_number
            cursor.execute("SELECT telegram_id FROM users GROUP BY telegram_id HAVING COUNT(*) > 1")
            duplicate_tg_ids = [str(row[0]) for row in cursor.fetchall()]
            
            cursor.execute("SELECT phone_number FROM users GROUP BY phone_number HAVING COUNT(*) > 1")
            duplicate_phones = [row[0] for row in cursor.fetchall()]
            
            cursor.execute("SELECT id, telegram_id, response_date, name, phone_number, email, english_level, modern_pc, hr "
                           "FROM users ORDER BY response_date DESC")
            rows = cursor.fetchall()
            conn.close()

            self.table.setRowCount(len(rows))
            
            # Группируем записи по дате и подсчитываем количество записей для каждой даты
            date_counts = {}
            for row_data in rows:
                timestamp = row_data[2]  # response_date
                if isinstance(timestamp, str):
                    date = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S").date()
                else:
                    date = timestamp.date()
                date_counts[date] = date_counts.get(date, 0) + 1

            # Обрабатываем записи и устанавливаем номера
            current_date = None
            current_count = 0
            
            for row_index, row_data in enumerate(rows):
                # Получаем дату из timestamp
                timestamp = row_data[2]
                if isinstance(timestamp, str):
                    date = datetime.strptime(timestamp, "%Y-%м-%d %H:%М:%S").date()
                else:
                    date = timestamp.date()
                
                # Если новая дата, сбрасываем счетчик
                if date != current_date:
                    current_date = date
                    current_count = date_counts[date]
                
                # Устанавливаем номер записи (от большего к меньшему)
                self.table.setVerticalHeaderItem(row_index, 
                    QtWidgets.QTableWidgetItem(str(current_count)))
                current_count -= 1
                
                # Заполняем данные строки
                for col_index, value in enumerate(row_data):
                    if col_index == 2 and value:  # Дата
                        if isinstance(value, datetime):
                            value = value.strftime("%d/%m/%y %H:%M")
                        else:
                            value = datetime.strptime(value, "%Y-%m-%d %H:%М:%S").strftime("%d/%м/%y %H:%М")
                    
                    item = QtWidgets.QTableWidgetItem(str(value) if value else "")
                    
                    # Подсветка дубликатов
                    if col_index == 1 and str(value) in duplicate_tg_ids:  # telegram_id
                        item.setBackground(QtGui.QColor(255, 200, 200))
                    elif col_index == 4 and value in duplicate_phones:  # phone_number
                        item.setBackground(QtGui.QColor(255, 200, 200))
                    elif col_index == 8 and (value is None or value == ""):  # hr
                        item.setBackground(QtGui.QColor(255, 150, 150))
                        
                    self.table.setItem(row_index, col_index, item)
            print("Data loaded successfully")
        except Exception as e:
            print(f"Error loading data: {e}")

        # Устанавливаем нужную ширину столбцов
        self.table.setColumnWidth(0, 50)   # id
        self.table.setColumnWidth(1, 80)   # telegram_id
        self.table.resizeColumnToContents(2)  # response_date
        self.table.setColumnWidth(3, 140)  # name
        self.table.setColumnWidth(4, 140)  # phone_number
        self.table.setColumnWidth(5, 140)  # email
        self.table.setColumnWidth(6, 40)   # english_level
        self.table.setColumnWidth(7, 40)   # modern_pc

    def apply_filters(self):
        searchable_columns = [0, 1, 2, 3, 4, 8]  # убираем 5, 6 (english_level, modern_pc)
        for row in range(self.table.rowCount()):
            self.table.setRowHidden(row, False)
        for row in range(self.table.rowCount()):
            for col_index, edit in zip(searchable_columns, self.search_edits):
                text = edit.text().lower()
                item = self.table.item(row, col_index)
                if item:
                    cell_value = item.text().lower()
                    if text and text not in cell_value:
                        self.table.setRowHidden(row, True)
                        break

    def delete_record(self):
        selected_items = self.table.selectedItems()
        if selected_items:
            id_item = selected_items[0]
            id_value = id_item.text()
            reply = QtWidgets.QMessageBox.question(self, 'Подтверждение', f"Удалить запись с ID {id_value}?",
                                                   QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.No)
            if reply == QtWidgets.QMessageBox.Yes:
                try:
                    conn = mysql.connector.connect(**self.config)
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM users WHERE id = %s", (id_value,))
                    conn.commit()
                    conn.close()
                    self.load_data()
                    print(f"Record with ID {id_value} deleted successfully")
                except Exception as e:
                    print(f"Error deleting record: {e}")

    def load_approved(self):
        try:
            with open("db3.txt", "r") as file:
                lines = file.readlines()
                db3_config = {
                    "host": lines[0].strip(),
                    "user": lines[1].strip(),
                    "password": lines[2].strip(),
                    "database": "TranslatorDB",
                    "port": int(lines[4].strip()),
                }
            
            conn = mysql.connector.connect(**db3_config)
            cursor = conn.cursor()
            
            # Для отладки - посмотрим структуру таблицы
            cursor.execute("DESCRIBE Workers")
            columns = cursor.fetchall()
            print("Table structure:", [col[0] for col in columns])
            
            cursor.execute("""
                SELECT Status, Date, Name, Country, Admin, Stage, RejectReason 
                FROM Workers 
                ORDER BY Date DESC
            """)
            
            rows = cursor.fetchall()
            conn.close()

            self.approved_table.setRowCount(len(rows))
            for row_index, row_data in enumerate(rows):
                for col_index, value in enumerate(row_data):
                    if col_index == 1 and value:  # Date
                        if isinstance(value, datetime):
                            value = value.strftime("%d/%m/%y %H:%M")
                        else:
                            value = datetime.strptime(str(value), "%Y-%m-%d %H:%M:%S").strftime("%d/%m/%y %H:%М")
                    item = QtWidgets.QTableWidgetItem(str(value) if value else "")
                    
                    # Подсветка дубликатов
                    if col_index == 0:  # Status column
                        if value == "NEW":
                            item.setBackground(QtGui.QColor(255, 255, 200))
                        elif value == "STUDY":
                            item.setBackground(QtGui.QColor(200, 255, 200))
                        elif value == "WORK":
                            item.setBackground(QtGui.QColor(200, 200, 255))
                        elif value == "LEFT":
                            item.setBackground(QtGui.QColor(255, 200, 200))
                    
                    self.approved_table.setItem(row_index, col_index, item)

            # Устанавливаем ширину столбцов
            self.approved_table.setColumnWidth(0, 80)   # Status
            self.approved_table.setColumnWidth(1, 100)  # Date
            self.approved_table.setColumnWidth(2, 150)  # Name
            self.approved_table.setColumnWidth(3, 100)  # Country
            self.approved_table.setColumnWidth(4, 100)  # Admin
            self.approved_table.setColumnWidth(5, 80)   # Stage
            self.approved_table.setColumnWidth(6, 150)  # RejectReason
            
            print("Approved data loaded successfully")
            
        except Exception as e:
            print(f"Error loading approved data: {e}")
            print(f"Error details: {str(e)}")

    def apply_approved_filters(self):
        status_filter = self.status_combo.currentText()
        admin_filter = self.admin_combo.currentText()
        name_filter = self.name_search.text().lower()
        
        for row in range(self.approved_table.rowCount()):
            should_show = True
            
            # Проверяем статус
            if status_filter != "All":
                status_item = self.approved_table.item(row, 0)
                if status_item and status_item.text().strip().upper() != status_filter.strip().upper():
                    should_show = False
            
            # Проверяем админа
            if admin_filter != "All":
                admin_item = self.approved_table.item(row, 4)
                if admin_item and admin_item.text() != admin_filter:
                    should_show = False
            
            # Проверяем имя
            if name_filter:
                name_item = self.approved_table.item(row, 2)
                if not (name_item and name_filter in name_item.text().lower()):
                    should_show = False
            
            self.approved_table.setRowHidden(row, not should_show)

    def assign_admin(self):
        selected_items = self.approved_table.selectedItems()
        if not selected_items:
            return
            
        row = selected_items[0].row()
        admin_item = self.approved_table.item(row, 4)
        if admin_item and admin_item.text():
            QtWidgets.QMessageBox.warning(self, "Warning", "Admin already assigned!")
            return
            
        # Используем список админов из admins.txt
        try:
            with open("admins.txt", "r") as file:
                admins = [line.strip() for line in file]
        except Exception as e:
            print(f"Error loading admins list: {e}")
            return
            
        admin, ok = QtWidgets.QInputDialog.getItem(
            self, "Select Admin", "Choose admin:", admins, 0, False
        )
        
        if ok and admin:
            try:
                # Обновляем базу данных
                with open("db3.txt", "r") as file:
                    lines = file.readlines()
                    db3_config = dict(zip(
                        ["host", "user", "password", "database", "port"],
                        [line.strip() for line in lines]
                    ))
                
                conn = mysql.connector.connect(**db3_config)
                cursor = conn.cursor()
                
                name_item = self.approved_table.item(row, 2)
                cursor.execute(
                    "UPDATE Workers SET admin = %s WHERE name = %s",  # Исправляем имя таблицы здесь тоже
                    (admin, name_item.text())
                )
                conn.commit()
                conn.close()
                
                # Отправляем уведомление в Telegram
                self.notify_admin_telegram(admin)
                
                # Обновляем таблицу
                self.load_approved()
                
            except Exception as e:
                print(f"Error assigning admin: {e}")
                QtWidgets.QMessageBox.warning(self, "Error", f"Failed to assign admin: {str(e)}")

    def notify_admin_telegram(self, admin_name):
        try:
            print("Sending notification to admin:", admin_name)
            with open("telegramAdmin.txt", "r") as file:
                api_token = file.read().strip()
            print("Telegram token:", api_token)

            response = requests.get(f"https://rabotabox.online/assets/HR/{admin_name}.txt")
            if response.status_code == 200:
                lines = response.text.strip().split('\n')
                group_id = lines[1].strip()  # Берём вторую строку
                print("Group ID:", group_id)

                message = "🥁⏰🧰 New translator added to your account! Please contact him as soon as possible!"
                resp = requests.get(
                    f"https://api.telegram.org/bot{api_token}/sendMessage",
                    params={"chat_id": group_id, "text": message},
                )
                print("Telegram response code:", resp.status_code)
                print("Telegram response body:", resp.text)
            else:
                print("Failed to get group ID from server. Status:", response.status_code)
        except Exception as e:
            print(f"Error sending Telegram notification: {e}")

def main():
    print("Starting application...")
    app = QtWidgets.QApplication(sys.argv)
    
    # Устанавливаем стиль
    app.setStyle('Fusion')
    
    # Создаем и показываем главное окно
    window = MainWindow()
    window.resize(900, 500)
    window.show()
    
    print("Application started")
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()

# В конце файла добавьте функцию для генерации зашифрованного URL:
def generate_encrypted_url():
    key = Fernet.generate_key()
    f = Fernet(key)
    url = 'https://rabotabox.online/assets/HR/Stas.txt'
    encrypted_url = f.encrypt(url.encode())
    print(f"Key: {key}")
    print(f"Encrypted URL: {encrypted_url}")

# Раскомментируйте следующую строку, чтобы сгенерировать новый ключ и URL, затем закомментируйте обратно
# generate_encrypted_url()