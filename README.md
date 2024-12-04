# Best Notes
BestNotes is a Python recreation of the app/program GoodNotes, a note-taking application. 
The user gets to create a digital notebook 
where they can write down notes for class or personal uses like journaling.
Through either drawing by their mouse or a stylus, users can create drawings as well as hand-written notes 
that they can easily move around by using a select tool. The program will also have a text feature, 
that allows the user to type their notes, which is easily moveable through the select tool. 
The notebooks have an autosave feature that saves these notebooks to the user’s devices. 
This program also has a collaboration feature that allows users to work together on a notebook. 

![image](https://github.com/user-attachments/assets/32b973fa-7ff2-471e-81f0-33bcd8a35adf)

# How to run
- Download and run the main.exe file from the latest [release](https://github.com/cis3296f24/01-BestNotes/releases).
  
## Requirements
- Download VLC media player: https://www.videolan.org/vlc/
- Install Python: https://www.python.org/downloads/

# How to build
[BestNotes Project Board](https://github.com/orgs/cis3296f24/projects/94/)

### Windows instructions
#### PyCharm instructions
PDF Instructions for PyCharm: [BestNotes PyCharm Run Instructions.pdf](https://github.com/user-attachments/files/17853496/BestNotes.PyCharm.Run.Instructions.pdf)

## Setup Instructions

1. **Download Python**
   - Open the Command Prompt and type `python`. This will open the Microsoft Store to the Python software page.
   - Click `Get` to start the download.  
   **Note:** If you previously downloaded Python through [python.org](https://python.org), please re-download it through the Microsoft Store.

2. **Download and Install PyCharm**
   - Download and install PyCharm from [here](https://www.jetbrains.com/pycharm/).

3. **Install VLC Media Player**
   - Download and install VLC Media Player: [https://www.videolan.org/vlc/](https://www.videolan.org/vlc/).

4. **Clone the Repository**
   - Clone the repository into PyCharm using the repository URL.

5. **Configure Python Interpreter**
   - When you try to run `main.py`, you will get an error stating that no Python Interpreter is configured for the project. To fix this:
     1. Click `Configure Python Interpreter > Add New Interpreter > Add Local Interpreter`.
     2. In the **Add Python Interpreter** window, select your Python Interpreter (e.g., `"Base Python: Python 3.11.4"`) and click `OK`.  
        A virtual environment will be created.

6. **Install Dependencies**
   - Open the terminal in PyCharm and install the required dependencies:
     ```bash
     pip install pyside6
     pip install python-vlc
     ```

7. **Run the Application**
   - Once the dependencies are installed, you should be able to run `BestNotes` by executing `main.py` in PyCharm.



#### IntelliJ instructions
PDF Instructions: [Best Notes Windows Set Up Instructions.pdf](https://github.com/user-attachments/files/17853642/BestNotes.Windows.Set.Up.Instructions.pdf)

You will need to download python, ideally the latest version. You can download it from the following link:
https://www.python.org/downloads/

-	## Setup Instructions

1. **Download IntelliJ IDEA**
   - If you don't have IntelliJ, download and install the IDE from [here](https://www.jetbrains.com/idea/).
   - Clone the project into IntelliJ using the repository URL.

2. **Install VLC Media Player**
   - Download and install VLC Media Player: [https://www.videolan.org/vlc/](https://www.videolan.org/vlc/).

3. **Install Python Plugin for IntelliJ**
   - Ensure the Python plugin is installed in IntelliJ.

4. **Configure Python Interpreter**
   - When you try to run `main.py`, it will give a warning about a missing translator. To resolve this:
     1. Click `Configure Python Interpreter`.
     2. Add a new local interpreter:
        - On the left bar, select **Virtualenv Environment**.
        - Inside the Virtualenv Environment menu, create a new environment and click `OK`.

5. **Activate Virtual Environment and Install Dependencies**
   - Open a command prompt and navigate to the project folder:
     ```bash
     cd IdeaProjects\BestNotes
     ```
   - Activate the virtual environment:
     ```bash
     venv\Scripts\activate
     ```
   - Install required dependencies:
     ```bash
     pip install pyside6
     pip install python-vlc
     ```

6. **Run the Application**
   - Exit the command prompt and return to IntelliJ.
   - Run `main.py` from IntelliJ, and the application should pop up.



### Mac Instructions
PDF Instructions: [Best Notes Mac Set Up Instructions.pdf](https://github.com/user-attachments/files/17577744/Best.Notes.Mac.Set.Up.Instructions.pdf)

Once that is completed, do the following:
- Once the download has completed, return to IntelliJ and hit the play button to run main.py and use the application.

## Setup Instructions for macOS

1. **Download IntelliJ IDEA**  
   - Download the IntelliJ IDE from the following link:  
     [https://www.jetbrains.com/idea/download/?section=mac](https://www.jetbrains.com/idea/download/?section=mac)

2. **Download Python**  
   - Download the latest version of Python from the following link:  
     [https://www.python.org/downloads/](https://www.python.org/downloads/)

3. **Install VLC Media Player**  
   - Download and install VLC Media Player:  
     [https://www.videolan.org/vlc/](https://www.videolan.org/vlc/)

4. **Clone the Repository**  
   - Clone the repository into IntelliJ.  
   **Note:** Using `Documents` is a recommended choice.

5. **Configure Python Interpreter in IntelliJ**  
   - Open the repository in IntelliJ and navigate to `main.py`.  
   - In the upper-right corner, a link saying `Configure Python Interpreter` should appear. Click it to set up a virtual environment for the project.  
     1. In the dialogue box, look for the option to select the SDK (Software Development Kit). It will say `<No Project SDK>`. Click it and choose `Add Python SDK from Disk`.
     2. In the new dialogue box, the top option, `Virtualenv Environment`, should be highlighted by default. Ensure that `New environment` is selected.
     3. In the `Base Interpreter` box, IntelliJ should automatically detect the Python version you downloaded. If not, click the three dots (`...`) next to the box and manually navigate to your Python installation It will typically be under /usr/local/bin/python3.13 for example, if you downloaded python 3.13. Click OK to create the virtual environment

6. **Activate the Virtual Environment and Install Dependencies**  
   - Open the **Terminal**:
   - Navigate to the project directory using the `cd` command:
     ```bash
     cd Documents
     cd <01-BestNotes>
     ```
   - Activate the virtual environment:
     ```bash
     source venv/bin/activate
     ```
     You should see the terminal prompt change to include `(venv)` at the start.
   - Install the required dependencies:
     ```bash
     pip3 install pyside6
     pip install python-vlc
     ```

7. **Run the Application**  
   - Return to IntelliJ and click the play button to run `main.py`. The application should launch and be ready to use.

Credits: Contributing on the code from [WhiteBoard](https://github.com/Shabbar10/PySide-Whiteboard)

