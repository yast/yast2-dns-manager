from dialogs import DNS
from yast import import_module
import_module('Wizard')
import_module('UI')
import_module('Sequencer')
from yast import Wizard, UI, Sequencer, Symbol

def DNSSequence():
    aliases = {
        'dns' : [(lambda: DNS().Show())],
    }

    sequence = {
        'ws_start' : 'dns',
        'dns' : {
            Symbol('abort') : Symbol('abort'),
            Symbol('next') : Symbol('next'),
        },
    }

    Wizard.CreateDialog()
    Wizard.SetTitleIcon('yast2-dns-manager')

    ret = Sequencer.Run(aliases, sequence)

    UI.CloseDialog()
    return ret

