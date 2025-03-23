# -*- coding: UTF-8 -*-
# --------------------------------------------------------------------------
# Software:     InVesalius - Software de Reconstrucao 3D de Imagens Medicas
# Copyright:    (C) 2001  Centro de Pesquisas Renato Archer
# Homepage:     http://www.softwarepublico.gov.br
# Contact:      invesalius@cti.gov.br
# License:      GNU - GPL 2 (LICENSE.txt/LICENCA.txt)
# --------------------------------------------------------------------------

import wx

import invesalius.constants as const
from invesalius.i18n import tr as _


class NavigationTypeConfigDialog(wx.Dialog):
    """
    Dialog for configuring navigation type parameters
    """

    def __init__(
        self,
        parent,
        navigation,
        navigation_type=None,
        is_new=False,
        title=None,
        show_name_field=False,
    ):
        """
        Initialize the dialog

        Args:
            parent: The parent window
            navigation: The Navigation object
            navigation_type (str, optional): The navigation type to configure.
                                          If None, uses the current navigation type.
            is_new (bool): Whether this is a new navigation type
            title (str, optional): Custom title for the dialog
            show_name_field (bool): Whether to show a field for entering a new navigation type name
        """
        if title:
            dialog_title = title
        elif is_new:
            dialog_title = _("Create New Navigation Type")
        else:
            dialog_title = _("Configure Navigation Type")

        wx.Dialog.__init__(
            self, parent, -1, dialog_title, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
        )

        self.navigation = navigation
        self.is_new = is_new
        self.show_name_field = show_name_field
        self.navigation_type = navigation_type or navigation.GetNavigationType()
        self.params = navigation.GetNavigationTypeParameters(self.navigation_type).copy()
        self.new_navigation_type_name = ""

        # Initialize UI
        self._init_ui()
        self._populate_fields()

        # Set minimum size
        self.SetMinSize((500, 600))

    def _init_ui(self):
        """
        Initialize the UI components
        """
        # Create a scrolled window to hold all the content
        self.scroll_win = wx.ScrolledWindow(self, -1, style=wx.VSCROLL)
        self.scroll_win.SetScrollRate(0, 10)

        # Main sizer for the dialog
        dialog_sizer = wx.BoxSizer(wx.VERTICAL)

        # Sizer for the scrolled window content
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # If creating a new type, show name field
        if self.show_name_field:
            name_sizer = wx.BoxSizer(wx.HORIZONTAL)
            name_label = wx.StaticText(self.scroll_win, -1, _("Navigation Type Name:"))
            self.name_field = wx.TextCtrl(self.scroll_win, -1, "")
            name_sizer.Add(name_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
            name_sizer.Add(self.name_field, 1, wx.ALL | wx.EXPAND, 5)
            main_sizer.Add(name_sizer, 0, wx.ALL | wx.EXPAND, 5)

            # Add separator
            main_sizer.Add(wx.StaticLine(self.scroll_win, -1), 0, wx.ALL | wx.EXPAND, 5)

        # Description
        desc_label = wx.StaticText(self.scroll_win, -1, _("Description:"))
        self.desc_field = wx.TextCtrl(self.scroll_win, -1, "", style=wx.TE_MULTILINE, size=(-1, 60))
        main_sizer.Add(desc_label, 0, wx.ALL, 5)
        main_sizer.Add(self.desc_field, 0, wx.ALL | wx.EXPAND, 5)

        # Add separator
        main_sizer.Add(wx.StaticLine(self.scroll_win, -1), 0, wx.ALL | wx.EXPAND, 5)

        # Timing parameters in a box
        timing_box = wx.StaticBox(self.scroll_win, -1, _("Timing Parameters"))
        timing_sizer = wx.StaticBoxSizer(timing_box, wx.VERTICAL)

        # Navigation sleep
        nav_sleep_sizer = wx.BoxSizer(wx.HORIZONTAL)
        nav_sleep_label = wx.StaticText(timing_box, -1, _("Navigation Sleep (s):"))
        self.nav_sleep_ctrl = wx.SpinCtrlDouble(timing_box, -1, "", inc=0.01)
        self.nav_sleep_ctrl.SetRange(0.01, 1.0)
        nav_sleep_sizer.Add(nav_sleep_label, 1, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        nav_sleep_sizer.Add(self.nav_sleep_ctrl, 0, wx.ALL, 5)
        timing_sizer.Add(nav_sleep_sizer, 0, wx.ALL | wx.EXPAND, 5)

        # Coordinate sleep
        coord_sleep_sizer = wx.BoxSizer(wx.HORIZONTAL)
        coord_sleep_label = wx.StaticText(timing_box, -1, _("Coordinate Sleep (s):"))
        self.coord_sleep_ctrl = wx.SpinCtrlDouble(timing_box, -1, "", inc=0.01)
        self.coord_sleep_ctrl.SetRange(0.01, 1.0)
        coord_sleep_sizer.Add(coord_sleep_label, 1, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        coord_sleep_sizer.Add(self.coord_sleep_ctrl, 0, wx.ALL, 5)
        timing_sizer.Add(coord_sleep_sizer, 0, wx.ALL | wx.EXPAND, 5)

        main_sizer.Add(timing_sizer, 0, wx.ALL | wx.EXPAND, 5)

        # Accuracy parameters in a box
        accuracy_box = wx.StaticBox(self.scroll_win, -1, _("Accuracy Parameters"))
        accuracy_sizer = wx.StaticBoxSizer(accuracy_box, wx.VERTICAL)

        # Calibration tracker samples
        samples_sizer = wx.BoxSizer(wx.HORIZONTAL)
        samples_label = wx.StaticText(accuracy_box, -1, _("Calibration Tracker Samples:"))
        self.samples_ctrl = wx.SpinCtrl(accuracy_box, -1, "")
        self.samples_ctrl.SetRange(1, 100)
        samples_sizer.Add(samples_label, 1, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        samples_sizer.Add(self.samples_ctrl, 0, wx.ALL, 5)
        accuracy_sizer.Add(samples_sizer, 0, wx.ALL | wx.EXPAND, 5)

        # Distance threshold
        dist_sizer = wx.BoxSizer(wx.HORIZONTAL)
        dist_label = wx.StaticText(accuracy_box, -1, _("Distance Threshold (mm):"))
        self.dist_ctrl = wx.SpinCtrl(accuracy_box, -1, "")
        self.dist_ctrl.SetRange(1, 10)
        dist_sizer.Add(dist_label, 1, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        dist_sizer.Add(self.dist_ctrl, 0, wx.ALL, 5)
        accuracy_sizer.Add(dist_sizer, 0, wx.ALL | wx.EXPAND, 5)

        # Angle threshold
        angle_sizer = wx.BoxSizer(wx.HORIZONTAL)
        angle_label = wx.StaticText(accuracy_box, -1, _("Angle Threshold (degrees):"))
        self.angle_ctrl = wx.SpinCtrl(accuracy_box, -1, "")
        self.angle_ctrl.SetRange(1, 10)
        angle_sizer.Add(angle_label, 1, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        angle_sizer.Add(self.angle_ctrl, 0, wx.ALL, 5)
        accuracy_sizer.Add(angle_sizer, 0, wx.ALL | wx.EXPAND, 5)

        # Coil angle arrow threshold
        coil_angle_sizer = wx.BoxSizer(wx.HORIZONTAL)
        coil_angle_label = wx.StaticText(accuracy_box, -1, _("Coil Angle Arrow Threshold:"))
        self.coil_angle_ctrl = wx.SpinCtrl(accuracy_box, -1, "")
        self.coil_angle_ctrl.SetRange(1, 10)
        coil_angle_sizer.Add(coil_angle_label, 1, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        coil_angle_sizer.Add(self.coil_angle_ctrl, 0, wx.ALL, 5)
        accuracy_sizer.Add(coil_angle_sizer, 0, wx.ALL | wx.EXPAND, 5)

        # FRE threshold
        fre_sizer = wx.BoxSizer(wx.HORIZONTAL)
        fre_label = wx.StaticText(accuracy_box, -1, _("FRE Threshold:"))
        self.fre_ctrl = wx.SpinCtrlDouble(accuracy_box, -1, "", inc=0.1)
        self.fre_ctrl.SetRange(0.5, 5.0)
        fre_sizer.Add(fre_label, 1, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        fre_sizer.Add(self.fre_ctrl, 0, wx.ALL, 5)
        accuracy_sizer.Add(fre_sizer, 0, wx.ALL | wx.EXPAND, 5)

        main_sizer.Add(accuracy_sizer, 0, wx.ALL | wx.EXPAND, 5)

        # Advanced parameters in a box
        advanced_box = wx.StaticBox(self.scroll_win, -1, _("Advanced Parameters"))
        advanced_sizer = wx.StaticBoxSizer(advanced_box, wx.VERTICAL)

        # Accuracy mode
        acc_mode_sizer = wx.BoxSizer(wx.HORIZONTAL)
        acc_mode_label = wx.StaticText(advanced_box, -1, _("Accuracy Mode:"))
        self.accuracy_combo = wx.Choice(
            advanced_box, -1, choices=[_("Standard"), _("High"), _("Maximum")]
        )
        acc_mode_sizer.Add(acc_mode_label, 1, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        acc_mode_sizer.Add(self.accuracy_combo, 0, wx.ALL, 5)
        advanced_sizer.Add(acc_mode_sizer, 0, wx.ALL | wx.EXPAND, 5)

        # Smoothing
        smoothing_sizer = wx.BoxSizer(wx.HORIZONTAL)
        smoothing_label = wx.StaticText(advanced_box, -1, _("Smoothing:"))
        self.smooth_check = wx.Choice(
            advanced_box, -1, choices=[_("None"), _("Light"), _("Medium"), _("Heavy")]
        )
        smoothing_sizer.Add(smoothing_label, 1, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        smoothing_sizer.Add(self.smooth_check, 0, wx.ALL, 5)
        advanced_sizer.Add(smoothing_sizer, 0, wx.ALL | wx.EXPAND, 5)

        main_sizer.Add(advanced_sizer, 0, wx.ALL | wx.EXPAND, 5)

        # Set the main sizer for the scrolled window
        self.scroll_win.SetSizer(main_sizer)
        self.scroll_win.Layout()

        # Create button sizer
        button_sizer = wx.StdDialogButtonSizer()
        if self.is_new:
            btn_ok = wx.Button(self, wx.ID_OK, _("Create"))
        else:
            btn_ok = wx.Button(self, wx.ID_OK, _("Apply"))
        btn_cancel = wx.Button(self, wx.ID_CANCEL)
        button_sizer.AddButton(btn_ok)
        button_sizer.AddButton(btn_cancel)
        button_sizer.Realize()

        # Add the scrolled window and buttons to the dialog sizer
        dialog_sizer.Add(self.scroll_win, 1, wx.EXPAND | wx.ALL, 5)
        dialog_sizer.Add(button_sizer, 0, wx.ALL | wx.ALIGN_CENTER, 10)

        self.SetSizer(dialog_sizer)

        # Set a reasonable size that fits most screens
        self.SetSize((550, 700))
        self.Layout()

        # Scroll to the top
        self.scroll_win.Scroll(0, 0)

    def _populate_fields(self):
        """
        Populate the fields with the current values
        """
        # Description
        self.desc_field.SetValue(self.params.get("description", ""))

        # Timing parameters
        self.nav_sleep_ctrl.SetValue(self.params.get("sleep_nav", const.SLEEP_NAVIGATION))
        self.coord_sleep_ctrl.SetValue(self.params.get("sleep_coord", const.SLEEP_COORDINATES))

        # Accuracy parameters
        self.samples_ctrl.SetValue(
            self.params.get("calibration_tracker_samples", const.CALIBRATION_TRACKER_SAMPLES)
        )
        self.dist_ctrl.SetValue(
            self.params.get("distance_threshold", const.DEFAULT_DISTANCE_THRESHOLD)
        )
        self.angle_ctrl.SetValue(self.params.get("angle_threshold", const.DEFAULT_ANGLE_THRESHOLD))
        self.coil_angle_ctrl.SetValue(
            self.params.get(
                "coil_angle_arrow_projection_threshold", const.COIL_ANGLE_ARROW_PROJECTION_THRESHOLD
            )
        )
        self.fre_ctrl.SetValue(
            self.params.get("fre_threshold", const.FIDUCIAL_REGISTRATION_ERROR_THRESHOLD)
        )

        # Advanced parameters
        self.accuracy_combo.SetSelection(self.params.get("accuracy_mode", 0))
        self.smooth_check.SetSelection(self.params.get("smoothing", 0))

    def GetParameters(self):
        """
        Get the parameters from the dialog

        Returns:
            dict: The parameters for the navigation type
        """
        params = self.params.copy()

        # Get the values from the UI controls
        params["description"] = self.desc_field.GetValue()
        params["sleep_nav"] = self.nav_sleep_ctrl.GetValue()
        params["sleep_coord"] = self.coord_sleep_ctrl.GetValue()
        params["calibration_tracker_samples"] = self.samples_ctrl.GetValue()
        params["distance_threshold"] = self.dist_ctrl.GetValue()
        params["angle_threshold"] = self.angle_ctrl.GetValue()
        params["coil_angle_arrow_projection_threshold"] = self.coil_angle_ctrl.GetValue()
        params["fre_threshold"] = self.fre_ctrl.GetValue()

        try:
            params["accuracy_mode"] = self.accuracy_combo.GetSelection()
            params["smoothing"] = self.smooth_check.GetSelection()
        except AttributeError:
            # Maintain existing values if controls weren't created
            pass

        return params

    def GetNavigationTypeName(self):
        """
        Get the name of the new navigation type

        Returns:
            str: The name of the new navigation type, or empty string if not applicable
        """
        if self.show_name_field and hasattr(self, "name_field"):
            return self.name_field.GetValue().strip()
        return ""

    def GetValue(self):
        """
        Legacy method for backwards compatibility

        Returns:
            tuple: (navigation_type_name, parameters)
        """
        params = self.GetParameters()

        # For backwards compatibility, return the navigation type name and parameters
        if self.show_name_field and hasattr(self, "name_field"):
            navigation_type = self.name_field.GetValue().strip()
        else:
            navigation_type = self.navigation_type

        return navigation_type, params
