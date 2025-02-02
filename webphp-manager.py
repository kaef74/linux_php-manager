import os
import re
import subprocess
from PyQt6.QtCore import QThread, pyqtSignal, QObject
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QPushButton,
    QLabel,
    QComboBox,
    QFileDialog,
    QMessageBox,
    QMenuBar,
    QMenu,
    QInputDialog,
    QProgressBar,
    QHBoxLayout
)
from PyQt6.QtGui import QAction


class PHPManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("WebPHP Manager")
        self.setGeometry(100, 100, 600, 200)

        self.layout = QVBoxLayout(self)

        # Меню
        self.menu_bar = QMenuBar(self)
        self.php_menu = QMenu("PHP", self)

        # Установка PHP
        self.install_php_action = QAction("Установить новую версию PHP", self)
        self.install_php_action.triggered.connect(self.prompt_install_php_version)
        self.php_menu.addAction(self.install_php_action)

        # Установка Composer
        self.install_composer_action = QAction("Установить Composer", self)
        self.install_composer_action.triggered.connect(self.prompt_install_composer)
        self.php_menu.addAction(self.install_composer_action)

        # Установка расширений
        self.install_extensions_action = QAction("Установить расширения", self)
        self.install_extensions_action.triggered.connect(self.prompt_install_php_extensions)
        self.php_menu.addAction(self.install_extensions_action)

        # Удаление
        self.uninstall_php_action = QAction("Удалить PHP и Composer", self)
        self.uninstall_php_action.triggered.connect(self.uninstall_php_composer)
        self.php_menu.addAction(self.uninstall_php_action)

        self.menu_bar.addMenu(self.php_menu)
        self.layout.setMenuBar(self.menu_bar)

        # Выбор версии PHP
        self.label = QLabel("Выберите глобальную версию PHP:")
        self.layout.addWidget(self.label)

        self.php_versions = self.get_installed_php_versions()
        self.php_selector = QComboBox()
        self.php_selector.addItems(self.php_versions)
        self.layout.addWidget(self.php_selector)

        # Кнопка переключения
        self.switch_button = QPushButton("Переключить глобальную версию")
        self.switch_button.clicked.connect(self.switch_global_php)
        self.layout.addWidget(self.switch_button)

        # Прогресс-бар и лейбл процентов (слева)
        progress_layout = QHBoxLayout()
        self.progress_label = QLabel("0%")
        self.progress_label.setFixedWidth(40)  # чтобы не «скакал» текст
        progress_layout.addWidget(self.progress_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #000000;
                background-color: #E0E0E0;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #0d6efd;
            }
        """)
        progress_layout.addWidget(self.progress_bar)

        self.layout.addLayout(progress_layout)
        self.setLayout(self.layout)

        self.update_interface()
        self.show()

    def on_progress(self, val: int):
        """
        Обновляет прогресс-бар и лейбл напрямую при получении новых данных о процентах.
        """
        if val < 0:
            val = 0
        if val > 100:
            val = 100
        self.progress_bar.setValue(val)
        self.progress_label.setText(f"{val}%")

    def prompt_install_php_version(self):
        method, ok = QInputDialog.getItem(
            self,
            "Выбор способа установки",
            "Выберите метод установки PHP:",
            ["Через репозиторий"], 0, False
        )
        if ok and method == "Через репозиторий":
            version, ok = QInputDialog.getText(
                self,
                "Выбор версии PHP",
                "Введите версию PHP для установки (например, 8.3):"
            )
            if ok and version:
                self.install_new_php_version(version)

    def prompt_install_composer(self):
        method, ok = QInputDialog.getItem(
            self,
            "Выбор способа установки",
            "Выберите метод установки Composer:",
            ["getcomposer.org"], 0, False
        )
        if ok and method == "getcomposer.org":
            self.install_composer()

    def prompt_install_php_extensions(self):
        # Получаем текущую выбранную версию PHP
        selected_version = self.php_selector.currentText()
        if not selected_version:
            QMessageBox.warning(self, "Нет версии", "Сначала выберите версию PHP в списке.")
            return

        # Спрашиваем у пользователя, какие расширения устанавливать
        extensions, ok = QInputDialog.getText(
            self,
            "Установить расширения",
            "Введите расширения через запятую (например: curl,xml,mysql):"
        )
        if ok and extensions.strip():
            # Сбрасываем прогресс
            self.on_progress(0)

            # Запускаем рабочий поток
            self.install_ext_worker = InstallPHPModulesWorker(selected_version, extensions)
            self.install_ext_worker.progress_signal.connect(self.on_progress)
            self.install_ext_worker.finished_signal.connect(self.on_install_finished)
            self.install_ext_worker.start()

    def install_new_php_version(self, version):
        self.on_progress(0)
        self.php_installer = InstallPHPWorker(version)
        self.php_installer.progress_signal.connect(self.on_progress)
        self.php_installer.finished_signal.connect(self.on_install_finished)
        self.php_installer.start()

    def install_composer(self):
        self.on_progress(0)
        self.composer_installer = InstallComposerWorker()
        self.composer_installer.progress_signal.connect(self.on_progress)
        self.composer_installer.finished_signal.connect(self.on_install_finished)
        self.composer_installer.start()

    def on_install_finished(self):
        self.on_progress(100)
        self.update_interface()

    def switch_global_php(self):
        selected_version = self.php_selector.currentText()
        if selected_version:
            # Убираем pkexec, т.к. приложение уже запущено под root (по аналогии с GParted)
            subprocess.run(
                ["update-alternatives", "--set", "php", f"/usr/bin/{selected_version}"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            self.label.setText(f"Текущая глобальная версия PHP: {selected_version}")
            self.update_interface()

    def uninstall_php_composer(self):
        confirm = QMessageBox.question(
            self,
            "Удаление PHP и Composer",
            "Вы уверены, что хотите полностью удалить PHP, Composer и Laravel Herd?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.on_progress(0)
            self.uninstall_worker = UninstallWorker()
            self.uninstall_worker.progress_signal.connect(self.on_progress)
            self.uninstall_worker.finished_signal.connect(self.on_uninstall_finished)
            self.uninstall_worker.start()

    def on_uninstall_finished(self):
        self.on_progress(100)
        QMessageBox.information(self, "Удаление завершено", "PHP, Composer и Laravel Herd были полностью удалены.")
        self.update_interface()

    def get_installed_php_versions(self):
        versions = []
        try:
            result = subprocess.run(["ls", "/usr/bin/"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
            for line in result.stdout.splitlines():
                if line.startswith("php") and line[3:].replace(".", "").isdigit():
                    versions.append(line)
            if os.path.exists(os.path.expanduser("~/.config/herd-lite/bin/php")):
                versions.append("php8.3 laravel")
        except FileNotFoundError:
            pass
        return sorted(set(versions)) if versions else []

    def update_interface(self):
        self.php_versions = self.get_installed_php_versions()
        self.php_selector.clear()
        self.php_selector.addItems(self.php_versions)


class BaseAptWorker(QThread, QObject):
    """
    Общий базовый класс с методом run_and_parse_progress,
    чтобы не дублировать код в каждом воркере.
    """
    progress_signal = pyqtSignal(int)

    def run_and_parse_progress(self, cmd_list):
        """
        Запускаем процесс через Popen, парсим вывод, ищем XX%.
        Если нашли — шлём сигнал progress_signal.emit(val).
        """
        process = subprocess.Popen(cmd_list, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        while True:
            line = process.stdout.readline()
            if not line:
                break
            found = re.findall(r"(\d+)%", line)
            if found:
                val = int(found[-1])
                self.progress_signal.emit(val)
        process.wait()


class InstallPHPWorker(BaseAptWorker):
    finished_signal = pyqtSignal()

    def __init__(self, version):
        super().__init__()
        self.version = version

    def run(self):
        # Добавляем репозиторий (убрали pkexec):
        self.run_and_parse_progress(["add-apt-repository", "ppa:ondrej/php", "-y"])

        # apt update
        self.run_and_parse_progress(["apt", "update"])

        # Установка PHP
        self.run_and_parse_progress(["apt", "install", f"php{self.version}", "-y"])

        self.finished_signal.emit()


class InstallComposerWorker(BaseAptWorker):
    finished_signal = pyqtSignal()

    def run(self):
        # Убираем pkexec из команд для Composer
        cmds = [
            ["php", "-r", 'copy("https://getcomposer.org/installer", "composer-setup.php");'],
            [
                "php", "-r",
                'if (hash_file("sha384", "composer-setup.php") === '
                '"dac665fdc30fdd8ec78b38b9800061b4150413ff2e3b6f88543c636f7cd84f6db9189d43a81e5503cda447da73c7e5b6") '
                '{ echo "Установщик проверен 100%"; } else { echo "Установщик поврежден 0%"; '
                'unlink("composer-setup.php"); } echo PHP_EOL;'
            ],
            ["php", "composer-setup.php"],
            ["php", "-r", 'unlink("composer-setup.php");'],
            ["mv", "composer.phar", "/usr/local/bin/composer"]
        ]

        for cmd in cmds:
            self.run_and_parse_progress(cmd)

        self.finished_signal.emit()


class InstallPHPModulesWorker(BaseAptWorker):
    finished_signal = pyqtSignal()

    def __init__(self, php_version, extensions_str):
        super().__init__()
        self.php_version = php_version
        self.extensions_str = extensions_str

    def run(self):
        # Разбиваем строку "curl,xml,mysql" -> ["curl","xml","mysql"] ...
        parts = self.extensions_str.split(",")
        ext_list = []
        for p in parts:
            ext = p.strip()
            if ext:
                base_ver = self.php_version.split()[0]  # например, "php8.3" из "php8.3 laravel"
                pkg = f"{base_ver}-{ext}"
                ext_list.append(pkg)

        if not ext_list:
            self.finished_signal.emit()
            return

        # Перед установкой - apt update
        self.run_and_parse_progress(["apt", "update"])

        # Установка всех перечисленных пакетов
        install_cmd = ["apt", "install", "-y"] + ext_list
        self.run_and_parse_progress(install_cmd)

        self.finished_signal.emit()


class UninstallWorker(BaseAptWorker):
    finished_signal = pyqtSignal()

    def run(self):
        # Удаляем php*
        self.run_and_parse_progress(["apt", "purge", "php*", "-y"])

        # Удаляем вручную всё остальное
        os.system("rm -rf /etc/php /usr/bin/php /usr/local/bin/php /usr/lib/php /usr/share/php /var/lib/php")
        os.system("rm -rf ~/.composer ~/.config/herd-lite")

        self.finished_signal.emit()


if __name__ == "__main__":
    app = QApplication([])
    window = PHPManager()
    window.show()
    app.exec()

