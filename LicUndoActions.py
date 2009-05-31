from PyQt4.QtGui import QUndoCommand
from PyQt4.QtCore import SIGNAL

import Helpers

NextCommandID = 122
def getNewCommandID():
    global NextCommandID
    NextCommandID += 1
    return NextCommandID

QUndoCommand.id = lambda self: self._id
QUndoCommand.undo = lambda self: self.doAction(False)
QUndoCommand.redo = lambda self: self.doAction(True)

class MoveCommand(QUndoCommand):

    """
    MoveCommand stores a list of parts moved together:
    itemList[0] = (item, item.oldPos, item.newPos)
    """

    _id = getNewCommandID()
    
    def __init__(self, itemList):
        QUndoCommand.__init__(self, "move Page Object")

        self.itemList = []
        for item in itemList:
            self.itemList.append((item, item.oldPos, item.pos()))

    def undo(self):
        for item, oldPos, newPos in self.itemList:
            item.setPos(oldPos)
            if hasattr(item.parentItem(), "resetRect"):
                item.parentItem().resetRect()

    def redo(self):
        for item, oldPos, newPos in self.itemList:
            item.setPos(newPos)
            if hasattr(item.parentItem(), "resetRect"):
                item.parentItem().resetRect()

class CalloutArrowMoveCommand(QUndoCommand):

    _id = getNewCommandID()

    def __init__(self, part, oldPoint, newPoint):
        QUndoCommand.__init__(self, "move Callout Arrow")
        self.part, self.oldPoint, self.newPoint = part, oldPoint, newPoint

    # Need to invalidate scene because we don't actually move a part here, so scene doesn't redraw
    def undo(self):
        self.part.point = self.oldPoint
        self.part.scene().invalidate(self.part.parentItem().boundingRect())

    def redo(self):
        self.part.point = self.newPoint
        self.part.scene().invalidate(self.part.parentItem().boundingRect())

class DisplacePartCommand(QUndoCommand):

    _id = getNewCommandID()

    def __init__(self, part, oldDisp, newDisp):
        QUndoCommand.__init__(self, "Part displacement")
        self.part, self.oldDisp, self.newDisp = part, oldDisp, newDisp

    def undo(self):
        self.part.displacement = list(self.oldDisp)
        self.part.getCSI().resetPixmap()

    def redo(self):
        self.part.displacement = list(self.newDisp)
        self.part.getCSI().resetPixmap()

class BeginDisplacementCommand(QUndoCommand):
    
    _id = getNewCommandID()

    def __init__(self, part, direction, arrow):
        QUndoCommand.__init__(self, "Begin Part displacement")
        self.part, self.direction, self.arrow = part, direction, arrow

    def undo(self):
        part = self.part
        part.displaceDirection = None
        part.displacement = []
        part.scene().emit(SIGNAL("layoutAboutToBeChanged()"))
        part.getCSI().removeArrow(self.arrow)
        part.scene().emit(SIGNAL("layoutChanged()"))
        part.getCSI().resetPixmap()

    def redo(self):
        part = self.part
        part.displaceDirection = self.direction
        part.displacement = Helpers.getDisplacementOffset(self.direction, True, part.partOGL.getBoundingBox())
        self.arrow.setPosition(*Helpers.GLMatrixToXYZ(part.matrix))
        self.arrow.adjustLength(Helpers.getOffsetFromBox(self.direction, part.partOGL.getBoundingBox()))
        part.scene().emit(SIGNAL("layoutAboutToBeChanged()"))
        part.getCSI().addArrow(self.arrow)
        part.scene().emit(SIGNAL("layoutChanged()"))
        part.getCSI().resetPixmap()
    
class ResizeCSIPLICommand(QUndoCommand):

    """
    ResizeCSIPLICommand stores a list of old / new image size pairs:
    sizes = ((oldCSISize, newCSISize), (oldPLISize, newPLISize))
    """

    _id = getNewCommandID()

    def __init__(self, instructions, sizes):
        QUndoCommand.__init__(self, "CSI | PLI resize")
        
        self.instructions = instructions
        csiSizes, pliSizes = sizes
        self.oldCSISize, self.newCSISize = csiSizes
        self.oldPLISize, self.newPLISize = pliSizes
        
    def undo(self):
        self.instructions.setCSIPLISize(self.oldCSISize, self.oldPLISize)
    
    def redo(self):
        self.instructions.setCSIPLISize(self.newCSISize, self.newPLISize)
    
    def mergeWith(self, command):
        
        if command.id() != self.id():
            return False
        
        self.newCSISize = command.newCSISize
        self.newPLISize = command.newPLISize
        return True

class ResizePageCommand(QUndoCommand):

    """
    ResizePageCommand stores a list of old / new page size and resolution pairs:
    sizes = ((oldPageSize, newPageSize), (oldRes, newRes))
    """

    _id = getNewCommandID()

    def __init__(self, instructions, sizes):
        QUndoCommand.__init__(self, "Undo the last Page resize")
        
        self.instructions = instructions
        csiSizes, pliSizes = sizes
        self.oldCSISize, self.newCSISize = csiSizes
        self.oldPLISize, self.newPLISize = pliSizes
        
    def undo(self):
        self.instructions.setCSIPLISize(self.oldCSISize, self.oldPLISize)
    
    def redo(self):
        self.instructions.setCSIPLISize(self.newCSISize, self.newPLISize)
    
    def mergeWith(self, command):
        
        if command.id() != self.id():
            return False
        
        self.newCSISize = command.newCSISize
        self.newPLISize = command.newPLISize
        return True

class MoveStepToPageCommand(QUndoCommand):

    """
    stepSet stores a list of (step, oldPage, newPage) tuples:
    stepSet = [(step1, oldPage1, newPage1), (step2, oldPage2, newPage2)]
    """

    _id = getNewCommandID()

    def __init__(self, stepSet):
        QUndoCommand.__init__(self, "move Step to Page")
        self.stepSet = stepSet

    def undo(self):
        for step, oldPage, newPage in self.stepSet:
            step.moveToPage(oldPage)
            oldPage.initLayout()
            newPage.initLayout()

    def redo(self):
        for step, oldPage, newPage in self.stepSet:
            step.moveToPage(newPage)
            newPage.initLayout()
            oldPage.initLayout()

class AddRemoveStepCommand(QUndoCommand):

    _id = getNewCommandID()

    def __init__(self, step, addStep):
        QUndoCommand.__init__(self, "%s Step" % ("add" if addStep else "delete"))
            
        self.step, self.addStep = step, addStep
        self.parent = step.parentItem()

    def doAction(self, redo):
        parent = self.parent
        if (redo and self.addStep) or (not redo and not self.addStep):
            parent.scene().emit(SIGNAL("layoutAboutToBeChanged()"))
            parent.insertStep(self.step)
            parent.scene().emit(SIGNAL("layoutChanged()"))
            self.step.setSelected(True)
        else:
            self.step.setSelected(False)
            parent.scene().emit(SIGNAL("layoutAboutToBeChanged()"))
            parent.deleteStep(self.step)                
            parent.scene().emit(SIGNAL("layoutChanged()"))
        parent.initLayout()

class AddRemoveCalloutCommand(QUndoCommand):

    _id = getNewCommandID()

    def __init__(self, callout, addCallout):
        QUndoCommand.__init__(self, "%s Callout" % ("add" if addCallout else "delete"))
            
        self.callout, self.addCallout = callout, addCallout
        self.parent = callout.parentItem()

    def doAction(self, redo):
        parent = self.parent
        if (redo and self.addCallout) or (not redo and not self.addCallout):
            parent.scene().emit(SIGNAL("layoutAboutToBeChanged()"))
            parent.addCallout(self.callout)
            parent.scene().emit(SIGNAL("layoutChanged()"))
            self.callout.setSelected(True)
        else:
            self.callout.setSelected(False)
            parent.scene().emit(SIGNAL("layoutAboutToBeChanged()"))
            parent.removeCallout(self.callout)                
            parent.scene().emit(SIGNAL("layoutChanged()"))
        parent.initLayout()

class AddRemovePageCommand(QUndoCommand):

    # TODO: Remove instructions.emit from here
    _id = getNewCommandID()

    def __init__(self, page, addPage):
        QUndoCommand.__init__(self, "%s Page" % ("add" if addPage else "delete"))
        self.page, self.addPage = page, addPage

    def doAction(self, redo):
        page = self.page
        page.instructions.emit(SIGNAL("layoutAboutToBeChanged()"))

        if (redo and self.addPage) or (not redo and not self.addPage):
            page.parent().addPage(page)
            number = page.number
        else:
            page.parent().deletePage(page)
            number = page.number - 1

        page.instructions.emit(SIGNAL("layoutChanged()"))
        page.instructions.scene.selectPage(number)

class AddRemoveGuideCommand(QUndoCommand):

    _id = getNewCommandID()

    def __init__(self, scene, guide, addGude):
        QUndoCommand.__init__(self, "%s Guide" % ("add" if addGude else "remove"))
        self.scene, self.guide, self.addGude = scene, guide, addGude

    def doAction(self, redo):

        if (redo and self.addGude) or (not redo and not self.addGude):
            self.scene.guides.append(self.guide)
            self.scene.addItem(self.guide)
        else:
            self.scene.removeItem(self.guide)
            self.scene.guides.remove(self.guide)

class MovePartsToStepCommand(QUndoCommand):

    _id = getNewCommandID()

    def __init__(self, partList, oldStep, newStep):
        QUndoCommand.__init__(self, "move Part to Step")
        self.partList, self.oldStep, self.newStep = partList, oldStep, newStep

    def moveFromStepToStep(self, oldStep, newStep):
        oldStep.scene().clearSelection()
        oldStep.scene().emit(SIGNAL("layoutAboutToBeChanged()"))

        for part in self.partList:
            oldStep.removePart(part)
            newStep.addPart(part)

        oldStep.scene().emit(SIGNAL("layoutChanged()"))

        oldStep.csi.resetPixmap()
        newStep.csi.resetPixmap()
        oldStep.parent().initLayout()
        newStep.parent().initLayout()
            
    def undo(self):
        self.moveFromStepToStep(self.newStep, self.oldStep)

    def redo(self):
        self.moveFromStepToStep(self.oldStep, self.newStep)

class AddPartsToCalloutCommand(QUndoCommand):

    _id = getNewCommandID()

    def __init__(self, callout, partList):
        QUndoCommand.__init__(self, "add Part to Callout")
        self.callout, self.partList = callout, partList

    def doAction(self, redo):
        self.callout.scene().emit(SIGNAL("layoutAboutToBeChanged()"))
        for part in self.partList:
            if redo:
                self.callout.addPart(part)
            else:
                self.callout.removePart(part)
        self.callout.scene().emit(SIGNAL("layoutChanged()"))
        self.callout.steps[-1].csi.resetPixmap()
        self.callout.initLayout()

class ToggleStepNumbersCommand(QUndoCommand):

    _id = getNewCommandID()

    def __init__(self, callout, enableNumbers):
        QUndoCommand.__init__(self, "%s Step Numbers" % ("show" if enableNumbers else "hide"))
        self.callout, self.enableNumbers = callout, enableNumbers

    def doAction(self, redo):
        self.callout.scene().emit(SIGNAL("layoutAboutToBeChanged()"))
        if (redo and self.enableNumbers) or (not redo and not self.enableNumbers):
            self.callout.enableStepNumbers()
        else:
            self.callout.disableStepNumbers()
        self.callout.scene().emit(SIGNAL("layoutChanged()"))
        self.callout.initLayout()

class ToggleCalloutQtyCommand(QUndoCommand):

    _id = getNewCommandID()

    def __init__(self, callout, enableQty):
        QUndoCommand.__init__(self, "%s Callout Quantity" % ("Add" if enableQty else "Remove"))
        self.callout, self.enableQty = callout, enableQty

    def doAction(self, redo):
        self.callout.scene().emit(SIGNAL("layoutAboutToBeChanged()"))
        if (redo and self.enableQty) or (not redo and not self.enableQty):
            self.callout.addQuantityLabel()
        else:
            self.callout.removeQuantityLabel()
        self.callout.scene().emit(SIGNAL("layoutChanged()"))
        self.callout.initLayout()
                
class AdjustArrowLength(QUndoCommand):

    _id = getNewCommandID()

    def __init__(self, arrow, offset):
        QUndoCommand.__init__(self, "arrow length change")
        self.arrow, self.offset = arrow, offset

    def undo(self):
        self.arrow.adjustLength(-self.offset)
        self.arrow.getCSI().resetPixmap()

    def redo(self):
        self.arrow.adjustLength(self.offset)
        self.arrow.getCSI().resetPixmap()

class RotateCSICommand(QUndoCommand):

    _id = getNewCommandID()

    def __init__(self, csi, rotation):
        QUndoCommand.__init__(self, "CSI rotation")
        self.csi, self.rotation = csi, rotation

    def undo(self):
        self.csi.rotation[0] -= self.rotation[0]
        self.csi.rotation[1] -= self.rotation[1]
        self.csi.rotation[2] -= self.rotation[2]
        self.csi.resetPixmap()

    def redo(self):
        self.csi.rotation[0] += self.rotation[0]
        self.csi.rotation[1] += self.rotation[1]
        self.csi.rotation[2] += self.rotation[2]
        self.csi.resetPixmap()
        