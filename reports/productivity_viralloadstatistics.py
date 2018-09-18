import os
from collections import OrderedDict

from DateTime import DateTime
from bika.lims import api
from bika.lims.browser import BrowserView
from bika.lims.browser.reports.selection_macros import SelectionMacrosView
from bika.lims.catalog import CATALOG_ANALYSIS_LISTING
from bika.lims.catalog import CATALOG_ANALYSIS_REQUEST_LISTING
from openpyxl import load_workbook
from openpyxl.writer.excel import save_virtual_workbook
from plone.app.layout.globals.interfaces import IViewView
from plone.memoize import view as viewcache
from zope.interface import implements
from bika.lims import logger
import calendar
import datetime

XLS_TEMPLATE = "ViralLoadStatistics.xlsx"
SHEET_STATISTICS = "VIRAL LOAD STATISTICS"

def save_in_memory_and_return(wb):
    virtual_workbook = save_virtual_workbook(wb)
    return {'report_title': "Saving report",
            'is_excel': True,
            'report_data': virtual_workbook}


class Report(BrowserView):
    implements(IViewView)

    def __init__(self, context, request, report=None):
        BrowserView.__init__(self, context, request)
        self.report = report
        self.selection_macros = SelectionMacrosView(self.context, self.request)
        self.cells = dict()
        self.workbook = None

    def __call__(self):
        year = int(self.request.form.get('year_viralloadstatistics', DateTime().year()))
        month = int(self.request.form.get('month_viralloadstatistics', "1"))
        category_uid = self.request.form.get('CategoryUID', None)
        if not category_uid:
            return

        logger.warn("year:{}".format(year))
        logger.warn("month:{}".format(month))
        last_day = calendar.monthrange(year, month)[1]
        date_from = "{}-{}-01".format(year, month)
        date_to = "{}-{}-{}".format(year, month, last_day)
        date_from = api.to_date(date_from, DateTime())
        date_to = api.to_date(date_to, DateTime())

        this_dir = os.path.dirname(os.path.abspath(__file__))
        templates_dir = os.path.join(this_dir, 'excel_files')
        wb_path = '/'.join([templates_dir, XLS_TEMPLATE])
        self.workbook = load_workbook(wb_path)

        # Fill statistics' header sheet
        ws_stats = self.workbook.get_sheet_by_name(SHEET_STATISTICS)
        month_name = datetime.date(year, month, 1).strftime("%B")
        month_name = month_name.upper()
        ws_stats["C2"] = "REPORTING MONTH/YEAR: {}/{}".format(month_name, year)
        query = {
            'getCategoryUID': category_uid,
            'getDatePublished': {'query': [date_from, date_to],
                                 'range': 'min:max'},
            'review_state': ['verified', 'published'],
            'cancellation_state': 'active',
            'sort_on': 'getClientTitle',
            'sort_order': 'ascending'}

        catalog = api.get_tool(CATALOG_ANALYSIS_LISTING)
        for analysis_brain in catalog(query):
            patient_brain = self.get_patient_brain(analysis_brain)
            if not patient_brain:
                continue

            self.render_statistics_row(analysis_brain)

        # Fill statistics sheet
        row_num_start = 6
        row_num = row_num_start  # start on row number 6 (headers before)
        provinces_dict = self.cells.get(SHEET_STATISTICS, dict())
        provinces = provinces_dict.keys()
        provinces.sort()
        for province in provinces:
            logger.warn("Province: {}".format(province))
            districts_dict = provinces_dict.get(province)
            districts = districts_dict.keys()
            districts.sort()
            for district in districts:
                logger.warn("  District: {}".format(district))
                clients = districts_dict.get(district)
                for client_uid, row in clients.items():
                    logger.warn("    Client: {}".format(client_uid))
                    for column, cell_value in row.items():
                        cell_id = '{}{}'.format(column, row_num)
                        logger.warn("      {}: {}".format(cell_id, cell_value))
                        ws_stats[cell_id] = cell_value
                    cell_id = 'A{}'.format(row_num)
                    ws_stats[cell_id] = row_num - row_num_start + 1
                    row_num += 1

        # Save the file in memory
        return save_in_memory_and_return(self.workbook)

    def render_statistics_row(self, analysis_brain):
        lab = self.context.bika_setup.laboratory
        client_brain = self.get_client_brain(analysis_brain)
        if not client_brain:
            return
        patient_brain = self.get_patient_brain(analysis_brain)
        if not patient_brain:
            return

        # Column mappings
        LAB_KEY = 'B'
        PROVINCE = 'C'
        DISTRICT = 'D'
        CLIENT_NAME = 'E'
        CLIENT_CODE = 'F'
        NUM_REJECTIONS = 'G'
        VL_L14_LEQ1000 = 'H'
        VL_L14_G1000 = 'I'
        VL_MALE_LEQ1000 = 'J'
        VL_MALE_G1000 = 'K'
        VL_FEMALE_LEQ1000 = 'L'
        VL_FEMALE_G1000 = 'M'
        VL_SUBTOTAL_LEQ1000 = 'N'
        VL_SUBTOTAL_G1000 = 'O'
        VL_UNK_LEQ1000 = 'P'
        VL_UNK_G1000 = 'Q'
        VL_TOTAL_LEQ1000 = 'R'
        VL_TOTAL_G1000 = 'S'
        VL_TOTAL_CLIENT = 'T'

        province_rows = self.cells.get(SHEET_STATISTICS, dict())
        district_rows = province_rows.get(client_brain.getProvince, dict())
        client_rows = district_rows.get(client_brain.getDistrict, dict())
        row = client_rows.get(client_brain.UID, dict())
        row[LAB_KEY] = lab.getTaxNumber()
        row[PROVINCE] = client_brain.getProvince
        row[DISTRICT] = client_brain.getDistrict
        row[CLIENT_NAME] = client_brain.Title
        row[CLIENT_CODE] = client_brain.id

        result = self.to_float(analysis_brain.getResult)
        if result is None:
            # If result is None it is because we weren't able
            # to cast the result to float, and then we assume
            # it is a string. We have then two possibilities,
            # that the result is "invalid" or that "target
            # not detectable". If it is the latter we should
            # count it in the group <1000 copies/mL. This is
            # why in that case we set the result to 1.
            str_result = analysis_brain.getResult
            if str_result.lower() == "invalid":
                return
            else:
                result = 1
        elif result == 3:
            # https://naralabs.atlassian.net/browse/NMRL-462
            # When the result is 3 it means "Collect new sample"
            # so we also skip it.
            return

        # Number of rejections
        rejections = analysis_brain.review_state in ['rejected'] and 1 or 0
        row[NUM_REJECTIONS] = row.get(NUM_REJECTIONS, 0) + rejections

        # Viral Load <14 yrs <=100 copies/ml (Peds)
        age = self.get_age(patient_brain)
        if age is None:
            # Unknown age
            if result <= 1000:
                row[VL_UNK_LEQ1000] = row.get(VL_UNK_LEQ1000, 0) + 1
            else:
                row[VL_UNK_G1000] = row.get(VL_UNK_G1000, 0) + 1
        elif age < 14:
            if result <= 1000:
                row[VL_L14_LEQ1000] = row.get(VL_L14_LEQ1000, 0) + 1
                row[VL_SUBTOTAL_LEQ1000] = row.get(VL_SUBTOTAL_LEQ1000, 0) + 1
            else:
                row[VL_L14_G1000] = row.get(VL_L14_G1000, 0) + 1
                row[VL_SUBTOTAL_G1000] = row.get(VL_SUBTOTAL_G1000, 0) + 1
        else:
            # Adult
            sex = patient_brain.getGender
            if sex == 'male':
                if result <= 1000:
                    row[VL_MALE_LEQ1000] = row.get(VL_MALE_LEQ1000, 0) + 1
                    row[VL_SUBTOTAL_LEQ1000] = row.get(VL_SUBTOTAL_LEQ1000, 0) + 1
                else:
                    row[VL_MALE_G1000] = row.get(VL_MALE_G1000, 0) + 1
                    row[VL_SUBTOTAL_G1000] = row.get(VL_SUBTOTAL_G1000, 0) + 1
            elif sex == 'female':
                if result <= 1000:
                    row[VL_FEMALE_LEQ1000] = row.get(VL_FEMALE_LEQ1000, 0) + 1
                    row[VL_SUBTOTAL_LEQ1000] = row.get(VL_SUBTOTAL_LEQ1000, 0) + 1
                else:
                    row[VL_FEMALE_G1000] = row.get(VL_FEMALE_G1000, 0) + 1
                    row[VL_SUBTOTAL_G1000] = row.get(VL_SUBTOTAL_G1000, 0) + 1
            else:
                # Unknown sex
                if result <= 1000:
                    row[VL_UNK_LEQ1000] = row.get(VL_UNK_LEQ1000, 0) + 1
                else:
                    row[VL_UNK_G1000] = row.get(VL_UNK_G1000, 0) + 1

        if result <= 1000:
            row[VL_TOTAL_LEQ1000] = row.get(VL_TOTAL_LEQ1000, 0) + 1
        else:
            row[VL_TOTAL_G1000] = row.get(VL_TOTAL_G1000, 0) + 1

        row[VL_TOTAL_CLIENT] = row.get(VL_TOTAL_CLIENT, 0) + 1

        client_rows[client_brain.UID] = row
        district_rows[client_brain.getDistrict] = client_rows
        province_rows[client_brain.getProvince] = district_rows
        self.cells[SHEET_STATISTICS] = province_rows

    def get_age(self, patient_brain):
        age_splitted = patient_brain.getAgeSplittedStr
        if not age_splitted:
            return None

        age = 0
        if age_splitted.find("y") > 0:
            age = self.to_float(age_splitted[0:age_splitted.find("y")])
            if not age:
                return None
        return age

    def get_sex(self, analysis_brain):
        patient_brain = self.get_patient_brain(analysis_brain)
        if not patient_brain:
            return None
        return patient_brain.getGender

    def to_float(self, value):
        try:
            return float(value)
        except:
            return None

    @viewcache.memoize
    def get_brain(self, uid, catalog):
        cat = api.get_tool(catalog)
        brain = cat(UID=uid)
        if not brain or len(brain) == 0:
            return None
        return brain[0]

    @viewcache.memoize
    def get_object(self, brain_or_object_or_uid):
        """Get the full content object. Returns None if the param passed in is
        not a valid, not a valid object or not found

        :param brain_or_object_or_uid: UID/Catalog brain/content object
        :returns: content object
        """
        if api.is_uid(brain_or_object_or_uid):
            return api.get_object_by_uid(brain_or_object_or_uid, default=None)
        if api.is_object(brain_or_object_or_uid):
            return api.get_object(brain_or_object_or_uid)
        return None

    def get_ar_brain(self, analysis_brain):
        ar_uid = analysis_brain.getParentUID
        if not ar_uid:
            return None
        return self.get_brain(ar_uid, CATALOG_ANALYSIS_REQUEST_LISTING)

    def get_client_brain(self, analysis_brain):
        ar = self.get_ar_brain(analysis_brain)
        if not ar:
            return None
        client_uid = ar.getClientUID
        if not client_uid:
            return None
        return self.get_brain(client_uid, 'portal_catalog')

    def get_patient_brain(self, analysis_brain):
        ar = self.get_ar_brain(analysis_brain)
        if not ar:
            return None
        patient_uid = ar.getPatientUID
        if not patient_uid:
            return None
        patient = self.get_brain(patient_uid, 'bikahealth_catalog_patient_listing')
        return patient
