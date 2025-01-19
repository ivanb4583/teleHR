import sys
import requests
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
        
        layout = QtWidgets.QVBoxLayout(self)
        
        # Поля ввода
        self.login = QtWidgets.QLineEdit()
        self.login.setPlaceholderText("Login")
        layout.addWidget(self.login)
        
        self.password = QtWidgets.QLineEdit()
        self.password.setPlaceholderText("Password")
        self.password.setEchoMode(QtWidgets.QLineEdit.Password)
        layout.addWidget(self.password)
        
        # Кнопка входа
        self.login_button = QtWidgets.QPushButton("Вход")
        self.login_button.clicked.connect(self.check_credentials)
        layout.addWidget(self.login_button)
        
        self.error_label = QtWidgets.QLabel("")
        self.error_label.setStyleSheet("color: red")
        layout.addWidget(self.error_label)
        
    def check_credentials(self):
        try:
            response = requests.get('https://rabotabox.online/assets/HR/Stas.txt')
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
        
        self.load_data()
        self.load_reviews()

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
            for row_index, row_data in enumerate(rows):
                for col_index, value in enumerate(row_data):
                    if col_index == 2 and value:  # Дата
                        if isinstance(value, datetime):
                            value = value.strftime("%d/%m/%y %H:%M")
                        else:
                            value = datetime.strptime(value, "%Y-%m-%d %H:%M:%S").strftime("%d/%m/%y %H:%M")
                    
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