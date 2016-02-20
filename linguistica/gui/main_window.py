import os
import time
from pathlib import Path

from networkx.readwrite import json_graph

from PyQt5.QtCore import (Qt, QUrl, QCoreApplication)
from PyQt5.QtWidgets import (QMainWindow, QWidget, QAction, QVBoxLayout,
                             QTreeWidget, QFileDialog, QLabel, QTreeWidgetItem,
                             QTableWidget, QTableWidgetItem, QSplitter,
                             QProgressDialog, QDialog, QGridLayout)
from PyQt5.QtWebKitWidgets import QWebView

from linguistica import read_corpus

from linguistica.util import (SEP_SIG, SEP_NGRAM, double_sorted, json_dump)

from linguistica.gui.worker import LinguisticaWorker

from linguistica.gui.util import (MAIN_WINDOW_WIDTH, MAIN_WINDOW_HEIGHT,
                                  TREEWIDGET_WIDTH_MIN, TREEWIDGET_WIDTH_MAX,
                                  TREEWIDGET_HEIGHT_MIN,
                                  WORDLIST, WORD_NGRAMS, BIGRAMS, TRIGRAMS,
                                  SIGNATURES, SIGS_TO_STEMS, WORDS_TO_SIGS,
                                  TRIES, WORDS_AS_TRIES, SUCCESSORS, PREDECESSORS,
                                  PHONOLOGY, PHONES, BIPHONES, TRIPHONES,
                                  MANIFOLDS, WORD_NEIGHBORS, VISUALIZED_GRAPH,
                                  SHOW_MANIFOLD_HTML)


def process_all_gui_events():
    QCoreApplication.processEvents()


# noinspection PyAttributeOutsideInit
class MainWindow(QMainWindow):
    def __init__(self, screen_height, screen_width, version, parent=None):
        super(MainWindow, self).__init__(parent)

        self.screen_width = screen_width
        self.screen_height = screen_height
        self.version = version

        # basic main window settings
        self.resize(MAIN_WINDOW_WIDTH, MAIN_WINDOW_HEIGHT)
        self.setWindowTitle('Linguistica {}'.format(self.version))

        # lexicon and lexicon tree
        self.lexicon_tree = QTreeWidget()
        self.lexicon_tree.setEnabled(True)
        self.lexicon_tree.setMinimumWidth(TREEWIDGET_WIDTH_MIN)
        self.lexicon_tree.setMaximumWidth(TREEWIDGET_WIDTH_MAX)
        self.lexicon_tree.setMinimumHeight(TREEWIDGET_HEIGHT_MIN)
        self.lexicon_tree.setHeaderLabel('')
        self.lexicon_tree.setItemsExpandable(True)
        # noinspection PyUnresolvedReferences
        self.lexicon_tree.itemClicked.connect(self.tree_item_clicked)

        # set up major display, parameter window, then load main window
        self.majorDisplay = QWidget()
        self.parameterWindow = QWidget()
        self.load_main_window()

        # 'File' menu and actions
        file_read_corpus_action = self.create_action(text='&Read corpus...',
                                                     slot=self.file_new_corpus_dialog,
                                                     tip='Open a corpus file',
                                                     shortcut='Ctrl+N')
        file_run_corpus_action = self.create_action(text='&Rerun corpus...',
                                                    slot=self.run_corpus,
                                                    tip='Rerun a corpus file',
                                                    shortcut='Ctrl+D')
        # file_preferences_action = self.create_action(text='&Preferences',
        #     slot=self.filePreferencesDialog, tip='Preferences')

        file_menu = self.menuBar().addMenu('&File')
        file_menu.addActions((file_read_corpus_action, file_run_corpus_action))

        self.status = self.statusBar()
        self.status.setSizeGripEnabled(False)
        self.status.showMessage('No corpus text file loaded. '
                                'To select one: File --> Read corpus...')

    def create_action(self, text=None, slot=None, tip=None, shortcut=None,
                      checkable=False):
        """
        This create actions for the File menu, things like
        Read Corpus, Rerun Corpus etc
        """
        action = QAction(text, self)
        if shortcut:
            action.setShortcut(shortcut)
        if tip:
            action.setToolTip(tip)
            action.setStatusTip(tip)
        if slot:
            # noinspection PyUnresolvedReferences
            action.triggered.connect(slot)
        if checkable:
            action.setCheckable(True)
        return action

    def file_new_corpus_dialog(self):
        """
        Pop up the "open a file" dialog and ask for which corpus text file
        to use
        """
        open_dir = os.getcwd()
        # noinspection PyTypeChecker,PyCallByClass
        fname = QFileDialog.getOpenFileName(self, 'Open a new corpus data file',
                                            open_dir)
        process_all_gui_events()

        # HACK: fname is supposed to be a string (at least according to the
        # PyQt5 documentation), but for some reason fname is a tuple.
        # So we need this hack to make sure that fname is a string of a filename
        # -- Jackson Lee, 2015/06/22

        # update: it's turned out that this behavior is due to compatibility
        # between PyQt and PySide. The "tuple" behavior is in line with the
        # newer API2 for PyQt. (PyQt on python 3 uses API2 by default.)
        # more here: http://srinikom.github.io/pyside-bz-archive/343.html
        # so perhaps we keep our current hack for now?
        # -- Jackson Lee, 2015/08/24

        if fname and any(fname) and (type(fname) is tuple):
            self.corpus_filename = fname[0]
        else:
            # if this hack isn't needed somehow...
            self.corpus_filename = fname

        process_all_gui_events()

        if type(self.corpus_filename) != str:
            return

        # note that self.corpus_filename is an absolute full path
        self.corpus_name = os.path.basename(self.corpus_filename)
        self.corpus_stem_name = Path(self.corpus_name).stem

        self.lexicon = read_corpus(self.corpus_filename)

        self.run_corpus()

    def update_progress(self, progress_text, target_percentage, gradual=True):
        """
        Update the progress dialog. This function is triggered by the
        "progress_signal" emitted from the linguistica component worker thread.
        """
        self.progressDialog.setLabelText(progress_text)
        if gradual:
            current_percentage = self.progressDialog.value()
            for percentage in range(current_percentage, target_percentage + 1):
                self.progressDialog.setValue(percentage)
                process_all_gui_events()
                time.sleep(0.02)
        else:
            self.progressDialog.setValue(target_percentage)
            process_all_gui_events()

    def run_corpus(self):
        self.status.clearMessage()
        self.status.showMessage('Running the corpus {} now...'
                                .format(self.corpus_name))

        print('\nCorpus text file in use:\n{}\n'.format(self.corpus_filename),
              flush=True)

        # set up the Linguistica components worker
        # The worker is a QThread. We spawn this thread, and the linguistica
        # components run on this new thread but not the main thread for the GUI.
        # This makes the GUI still responsive
        # while the long and heavy running process of
        # the Linguistica components is ongoing.

        self.lxa_worker = LinguisticaWorker(self.lexicon)
        # self.lxa_worker.progress_signal.connect(self.update_progress)

        # set up progress dialog

        # self.progressDialog = QProgressDialog()
        # self.progressDialog.setRange(0, 100)  # it's like from 0% to 100%
        # self.progressDialog.setLabelText('Extracting word ngrams...')
        # self.progressDialog.setValue(0)  # initialize as 0 (= 0%)
        # self.progressDialog.setWindowTitle(
        #     'Processing {}'.format(self.corpus_name))
        # self.progressDialog.setCancelButton(None)
        # self.progressDialog.show()

        # We disable the "cancel" button
        # Setting up a "cancel" mechanism may not be a good idea,
        # since it would probably involve killing the linguistica component
        # worker at *any* point of its processing.
        # This may have undesirable effects (e.g., freezing the GUI) -- BAD!


        # make sure all GUI stuff up to this point has been processed before
        # doing the real work of running the Lxa components
        process_all_gui_events()

        # Now the real work begins here!
        self.lxa_worker.start()

        # if self.progressDialog.value() != 100:
        #     self.progressDialog.setValue(100)
        process_all_gui_events()

        self.lexicon = self.lxa_worker.get_lexicon()

        print('\nAll Linguistica components run for the corpus', flush=True)
        self.status.clearMessage()
        self.status.showMessage('{} processed'.format(self.corpus_name))

        self.populate_lexicon_tree()

    def populate_lexicon_tree(self):
        self.lexicon_tree.clear()

        # corpus name (in the tree header label)
        self.lexicon_tree.setHeaderLabel('Corpus: ' + self.corpus_name)

        # wordlist
        ancestor = QTreeWidgetItem(self.lexicon_tree, [WORDLIST])
        self.lexicon_tree.expandItem(ancestor)

        # word ngrams
        ancestor = QTreeWidgetItem(self.lexicon_tree, [WORD_NGRAMS])
        self.lexicon_tree.expandItem(ancestor)
        for item_str in [BIGRAMS, TRIGRAMS]:
            item = QTreeWidgetItem(ancestor, [item_str])
            self.lexicon_tree.expandItem(item)

        # signatures
        ancestor = QTreeWidgetItem(self.lexicon_tree, [SIGNATURES])
        self.lexicon_tree.expandItem(ancestor)
        for item in [SIGS_TO_STEMS, WORDS_TO_SIGS]:
            self.lexicon_tree.expandItem(QTreeWidgetItem(ancestor, [item]))

        # tries
        ancestor = QTreeWidgetItem(self.lexicon_tree, [TRIES])
        self.lexicon_tree.expandItem(ancestor)
        for item in [WORDS_AS_TRIES, SUCCESSORS, PREDECESSORS]:
            self.lexicon_tree.expandItem(QTreeWidgetItem(ancestor, [item]))

        # phonology
        ancestor = QTreeWidgetItem(self.lexicon_tree, [PHONOLOGY])
        self.lexicon_tree.expandItem(ancestor)
        for item in [PHONES, BIPHONES, TRIPHONES]:
            self.lexicon_tree.expandItem(QTreeWidgetItem(ancestor, [item]))

        # manifolds
        ancestor = QTreeWidgetItem(self.lexicon_tree, [MANIFOLDS])
        self.lexicon_tree.expandItem(ancestor)
        for item in [WORD_NEIGHBORS, VISUALIZED_GRAPH]:
            self.lexicon_tree.expandItem(QTreeWidgetItem(ancestor, [item]))

        self.status.clearMessage()
        self.status.showMessage('Navigation tree populated')
        print('Lexicon navigation tree populated', flush=True)

    def load_main_window(self, major_display=None, parameter_window=None):
        """
        Refresh the main window for the updated display content
        (most probably after a click or some event is triggered)
        """
        # get sizes of the three major PyQt objects
        major_display_size = self.majorDisplay.size()
        parameter_window_size = self.parameterWindow.size()
        lexicon_tree_size = self.lexicon_tree.size()

        if major_display:
            self.majorDisplay = major_display
        if parameter_window:
            self.parameterWindow = parameter_window

        # apply sizes to the major three objects
        self.majorDisplay.resize(major_display_size)
        self.parameterWindow.resize(parameter_window_size)
        self.lexicon_tree.resize(lexicon_tree_size)

        # set up:
        # 1) main splitter (b/w lexicon-tree+parameter window and major display)
        # 2) minor splitter (b/w lexicon-tree and parameter window)
        self.mainSplitter = QSplitter(Qt.Horizontal)
        self.mainSplitter.setHandleWidth(10)
        self.mainSplitter.setChildrenCollapsible(False)

        self.minorSplitter = QSplitter(Qt.Vertical)
        self.minorSplitter.setHandleWidth(10)
        self.minorSplitter.setChildrenCollapsible(False)

        self.minorSplitter.addWidget(self.lexicon_tree)
        self.minorSplitter.addWidget(self.parameterWindow)

        self.mainSplitter.addWidget(self.minorSplitter)
        self.mainSplitter.addWidget(self.majorDisplay)

        self.setCentralWidget(self.mainSplitter)

    def sig_to_stems_clicked(self, row):
        signature = self.sig_to_stems_major_table.item(row, 0).text()
        print(signature)
        signature = tuple(signature.split(SEP_SIG))

        stems = self.lexicon.signatures_to_stems()[signature]
        number_of_stems_per_column = 5

        # create a master list of sublists, where each sublist contains k stems
        # k = number_of_stems_per_column
        stem_rows = list()
        stem_row = list()

        for i, stem in enumerate(stems, 1):
            stem_row.append(stem)
            if not i % number_of_stems_per_column:
                stem_rows.append(stem_row)
                stem_row = list()
        if stem_row:
            stem_rows.append(stem_row)

        # set up the minor table as table widget
        sig_to_stems_minor_table = QTableWidget()
        sig_to_stems_minor_table.horizontalHeader().hide()
        sig_to_stems_minor_table.verticalHeader().hide()
        sig_to_stems_minor_table.clear()
        sig_to_stems_minor_table.setRowCount(len(stem_rows))
        sig_to_stems_minor_table.setColumnCount(number_of_stems_per_column)

        # fill in the minor table
        for row, stem_row in enumerate(stem_rows):
            for col, stem in enumerate(stem_row):
                item = QTableWidgetItem(stem)
                sig_to_stems_minor_table.setItem(row, col, item)

        sig_to_stems_minor_table.resizeColumnsToContents()

        minor_table_title = QLabel('{} (number of stems: {})'
                                   .format(SEP_SIG.join(signature), len(stems)))

        minor_table_widget_with_title = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(minor_table_title)
        layout.addWidget(sig_to_stems_minor_table)
        minor_table_widget_with_title.setLayout(layout)

        new_display = QSplitter(Qt.Horizontal)
        new_display.setHandleWidth(10)
        new_display.setChildrenCollapsible(False)

        new_display.addWidget(self.sig_to_stems_major_table)
        new_display.addWidget(minor_table_widget_with_title)
        new_display_width = self.majorDisplay.width() / 2
        new_display.setSizes(
            [new_display_width * 0.4, new_display_width * 0.6])

        self.load_main_window(major_display=new_display)
        self.status.clearMessage()
        self.status.showMessage('{} selected'.format(signature))

    def tree_item_clicked(self, item):
        """
        Trigger the appropriate action when something in the lexicon tree
        is clicked, and update the major display plus parameter window
        """
        item_str = item.text(0)

        if item_str in {WORD_NGRAMS, SIGNATURES, TRIES, PHONOLOGY, MANIFOLDS}:
            return

        print('loading', item_str, flush=True)

        self.status.clearMessage()
        self.status.showMessage('Loading {}...'.format(item_str))

        new_display = None
        new_parameter_window = None

        if item_str == WORDLIST:
            new_display = self.create_major_display_table(
                self.lexicon.word_unigram_counter().items(),
                key=lambda x: x[1], reverse=True, headers=['Word', 'Count'],
                row_cell_functions=[lambda x: x[0], lambda x: x[1]],
                cutoff=0)

        elif item_str == BIGRAMS:
            new_display = self.create_major_display_table(
                self.lexicon.word_bigram_counter().items(),
                key=lambda x: x[1], reverse=True,
                headers=['Bigram', 'Count'],
                row_cell_functions=[lambda x: SEP_NGRAM.join(x[0]),
                                    lambda x: x[1]],
                cutoff=2000)

        elif item_str == TRIGRAMS:
            new_display = self.create_major_display_table(
                self.lexicon.word_trigram_counter().items(),
                key=lambda x: x[1], reverse=True,
                headers=['Trigram', 'Count'],
                row_cell_functions=[lambda x: SEP_NGRAM.join(x[0]),
                                    lambda x: x[1]],
                cutoff=2000)

        elif item_str == SIGS_TO_STEMS:
            self.sig_to_stems_major_table = self.create_major_display_table(
                self.lexicon.signatures_to_stems().items(),
                key=lambda x: len(x[1]), reverse=True,
                headers=['Signature', 'Stem count', 'A few stems'],
                row_cell_functions=[lambda x: SEP_SIG.join(x[0]),
                                    lambda x: len(x[1]),
                                    lambda x: ', '.join(sorted(x[1])[:2]) +
                                              ', ...'],
                cutoff=0)
            # noinspection PyUnresolvedReferences
            self.sig_to_stems_major_table.cellClicked.connect(
                self.sig_to_stems_clicked)
            new_display = self.sig_to_stems_major_table

        elif item_str == WORDS_TO_SIGS:
            new_display = self.create_major_display_table(
                self.lexicon.words_to_signatures().items(),
                key=lambda x: len(x[1]), reverse=True,
                headers=['Word', 'Signature count', 'Signatures'],
                row_cell_functions=[lambda x: x[0],
                                    lambda x: len(x[1]),
                                    lambda x: ', '.join([SEP_SIG.join(sig)
                                                         for sig in
                                                         sorted(x[1])])],
                cutoff=2000)

        elif item_str == WORDS_AS_TRIES:
            words = self.lexicon.broken_words_left_to_right().keys()
            words_to_tries = dict()
            # key: word (str)
            # value: tuple of (str, str)
            # for left-to-right and right-to-left tries

            for word in words:
                l_r = ' '.join(self.lexicon.broken_words_left_to_right()[word])
                r_l = ' '.join(self.lexicon.broken_words_right_to_left()[word])
                words_to_tries[word] = (l_r, r_l)  # left-right, right-left

            new_display = self.create_major_display_table(
                words_to_tries.items(),
                key=lambda x: x[0], reverse=False,
                headers=['Word', 'Reversed word',
                         'Left-to-right trie', 'Right-to-left trie'],
                row_cell_functions=[lambda x: x[0], lambda x: x[0][::-1],
                                    lambda x: x[1][0], lambda x: x[1][1]],
                cutoff=0, set_text_alignment=[(3, Qt.AlignRight)])

        elif item_str == SUCCESSORS:
            new_display = self.create_major_display_table(
                self.lexicon.successors().items(),
                key=lambda x: len(x[1]), reverse=True,
                headers=['String', 'Successors'],
                row_cell_functions=[lambda x: x[0],
                                    lambda x: ', '.join(sorted(x[1]))],
                cutoff=0)

        elif item_str == PREDECESSORS:
            new_display = self.create_major_display_table(
                self.lexicon.predecessors().items(),
                key=lambda x: len(x[1]), reverse=True,
                headers=['String', 'Predecessors'],
                row_cell_functions=[lambda x: x[0],
                                    lambda x: ', '.join(sorted(x[1]))],
                cutoff=0)

        elif item_str == PHONES:
            new_display = self.create_major_display_table(
                self.lexicon.phone_unigram_counter().items(),
                key=lambda x: x[1], reverse=True,
                headers=['Phone', 'Count'],
                row_cell_functions=[lambda x: x[0], lambda x: x[1]],
                cutoff=0)

        elif item_str == BIPHONES:
            new_display = self.create_major_display_table(
                self.lexicon.phone_bigram_counter().items(),
                key=lambda x: x[1], reverse=True,
                headers=['Biphone', 'Count'],
                row_cell_functions=[lambda x: SEP_NGRAM.join(x[0]),
                                    lambda x: x[1]],
                cutoff=0)

        elif item_str == TRIPHONES:
            new_display = self.create_major_display_table(
                self.lexicon.phone_trigram_counter().items(),
                key=lambda x: x[1], reverse=True,
                headers=['Triphone', 'Count'],
                row_cell_functions=[lambda x: SEP_NGRAM.join(x[0]),
                                    lambda x: x[1]],
                cutoff=0)

        elif item_str == WORD_NEIGHBORS:
            word_to_freq = self.lexicon.word_unigram_counter()
            new_display = self.create_major_display_table(
                self.lexicon.words_to_neighbors().items(),
                key=lambda x: word_to_freq[x[0]], reverse=True,
                headers=['Word', 'Word count', 'Neighbors'],
                row_cell_functions=[lambda x: x[0],
                                    lambda x: word_to_freq[x[0]],
                                    lambda x: ' '.join(x[1])],
                cutoff=0)

        elif item_str == VISUALIZED_GRAPH:

            # TODO: Reorganize the visualization-related files
            # where should the "visualization" be? (rename it to "viz"?)
            # is there a way to generate what d3 needs without having to
            # generate the html/javascript code and file

            graph_width = self.screen_width - TREEWIDGET_WIDTH_MAX - 50
            graph_height = self.screen_height - 70
            html_name = 'show_manifold.html'
            # html_name = '_test_show_manifold.html"

            manifold_name = '{}_{}_{}_manifold.json'.format(
                self.corpus_stem_name, 1000, 9)
            manifold_dir = os.getcwd()
            manifold_filename = os.path.join(manifold_dir, manifold_name)
            print('manifold_filename', manifold_filename)

            manifold_json_data = json_graph.node_link_data(
                self.lexicon.neighbor_graph())
            json_dump(manifold_json_data, open(manifold_filename, 'w'))

            viz_html = os.path.join(os.getcwd(), html_name)
            print('viz_html', viz_html)

            # write the show_manifold html file
            with open(viz_html, 'w') as f:
                print(SHOW_MANIFOLD_HTML.format(os.path.dirname(__file__),
                                                graph_width, graph_height,
                                                manifold_filename), file=f)

            url = Path(viz_html).as_uri()
            print('url:', url)

            new_display = QWebView()
            new_display.setUrl(QUrl(url))

        self.load_main_window(major_display=new_display,
                              parameter_window=new_parameter_window)

        self.status.clearMessage()
        self.status.showMessage('{} selected'.format(item_str))

    @staticmethod
    def create_major_display_table(input_iterable,
                                   key=lambda x: x, reverse=False,
                                   headers=None, row_cell_functions=None,
                                   cutoff=0,
                                   set_text_alignment=None):
        """
        This is a general function for creating a tabular display for the
        major display.
        """

        if not input_iterable:
            print('Warning: input is empty', flush=True)
            return

        if not hasattr(input_iterable, '__iter__'):
            print('Warning: input is not an iterable', flush=True)
            return

        number_of_headers = len(headers)
        number_of_columns = len(row_cell_functions)

        if number_of_headers != number_of_columns:
            print('headers and cell functions don\'t match', flush=True)
            return

        len_input = len(input_iterable)

        table_widget = QTableWidget()
        table_widget.clear()
        table_widget.setSortingEnabled(False)

        # set up row count
        if cutoff and cutoff < len_input:
            actual_cutoff = cutoff
        else:
            actual_cutoff = len_input

        table_widget.setRowCount(actual_cutoff)

        # set up column count and table headers
        table_widget.setColumnCount(number_of_headers)
        table_widget.setHorizontalHeaderLabels(headers)

        # fill in the table
        for row, x in enumerate(double_sorted(input_iterable, key=key,
                                              reverse=reverse)):
            for col, fn in enumerate(row_cell_functions):
                cell = fn(x)

                if isinstance(cell, (int, float)):
                    # cell is numeric
                    item = QTableWidgetItem()
                    item.setData(Qt.EditRole, cell)
                else:
                    # cell is not numeric
                    item = QTableWidgetItem(cell)

                if set_text_alignment:
                    for align_col, alignment in set_text_alignment:
                        if col == align_col:
                            item.setTextAlignment(alignment)

                table_widget.setItem(row, col, item)

            if not row < actual_cutoff:
                break

        table_widget.setSortingEnabled(True)
        table_widget.resizeColumnsToContents()

        return table_widget