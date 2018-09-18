import StringIO
import csv
import datetime

from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from bika.lims.catalog.analysisrequest_catalog import \
    CATALOG_ANALYSIS_REQUEST_LISTING
from plone.app.layout.globals.interfaces import IViewView
from zope.interface import implements

from bika.lims import bikaMessageFactory as _
from bika.lims import api
from bika.lims import logger
from bika.lims.browser import BrowserView
from bika.lims.browser.reports.selection_macros import SelectionMacrosView
from bika.lims.catalog import CATALOG_ANALYSIS_LISTING
from bika.lims.utils import t
from plone.memoize import view as viewcache

CATALOG_PATIENT_LISTING = 'bikahealth_catalog_patient_listing'


class Report(BrowserView):
    implements(IViewView)
    template = ViewPageTemplateFile("templates/report_out.pt")

    def __init__(self, context, request, report=None):
        BrowserView.__init__(self, context, request)
        self.report = report
        self.selection_macros = SelectionMacrosView(self.context, self.request)
        self.uids_map = dict()

    def __call__(self):
        # get all the data into datalines
        catalog = api.get_tool(CATALOG_ANALYSIS_LISTING, self.context)
        self.report_content = {}
        parms = []
        headings = {}
        headings['header'] = ""
        count_all = 0
        query = {}
        # Getting the query filters
        val = self.selection_macros.parse_client(self.request)
        if val:
            query[val['contentFilter'][0]] = val['contentFilter'][1]
            parms.append(val['parms'])

        val = self.selection_macros.parse_sampletype(self.request)
        if val:
            query[val['contentFilter'][0]] = val['contentFilter'][1]
            parms.append(val['parms'])

        val = self.selection_macros.parse_analysisservice(self.request)
        if val:
            query[val['contentFilter'][0]] = val['contentFilter'][1]
            parms.append(val['parms'])

        val = self.selection_macros.parse_daterange(self.request,
                                                    'created',
                                                    'Created')
        if val:
            query[val['contentFilter'][0]] = val['contentFilter'][1]
            parms.append(val['parms'])

        val = self.selection_macros.parse_daterange(self.request,
                                                    'getDatePublished',
                                                    'Date Published')

        if val:
            query[val['contentFilter'][0]] = val['contentFilter'][1]
            parms.append(val['parms'])

        val = self.selection_macros.parse_daterange(self.request,
                                                    'getDateReceived',
                                                    'Date Received')

        if val:
            query[val['contentFilter'][0]] = val['contentFilter'][1]
            parms.append(val['parms'])

        formats = {'columns': 25,
                   'col_heads': [
                       _('Lab Number'),
                       _('Testing Lab'),
                       _('First Name'),
                       _('Middle Name'),
                       _('Last Name'),
                       _('Gender'),
                       _('Age'),
                       _('Age Type'),
                       _('Town'),
                       _('Reporting County'),
                       _('Reporting District'),
                       _('Reporting Facility'),
                       _('Date Onset'),
                       _('Date of Reporting'),
                       _('Was Specimen collected? '),
                       _('Date specimen collected'),
                       _('Type of Specimen'),
                       _('Date Specimen Sent to Lab'),
                       _('Date Specimen Received in Lab'),
                       _('Date Published'),
                       _('Condition of Specimen'),
                       _('Comment'),
                       _('Test Result')], }
        # and now lets do the actual report lines
        datalines = []
        laboratory = self.context.bika_setup.laboratory

        # Get analyses brains
        logger.info("Searching Analyses: {}".format(repr(query)))
        brains = catalog(query)

        # Collect all AR uids and Patient UIDs so only one query to get all
        # them will be needed
        ar_uids = list(set([brain.getParentUID for brain in brains]))
        ar_uids = filter(None, ar_uids)
        self.map_uids_to_brains(ar_uids)

        logger.info("Filling datalines with {} Analyses".format(len(brains)))
        for analysis in brains:
            # We get the AR and the patient of the
            # analysis here to avoid having to get them
            # inside each of the following method calls.
            # If they are not found its value will be None
            ar_brain = self.get_ar_brain(analysis)
            patient_brain = self.get_patient_brain(analysis)

            dataline = []

            # Lab Number
            dataitem = self.get_lab_number(analysis)
            dataline.append(dataitem)

            # Testing Lab
            dataline.append({'value': laboratory.Title()})

            #First Name
            dataitem = self.get_firstname(patient_brain)
            dataline.append(dataitem)
            
            #Middle Name
            dataitem = self.get_middlename(patient_brain)
            dataline.append(dataitem)

            #Last Name
            dataitem = self.get_lastname(patient_brain)
            dataline.append(dataitem)

            #Gender
            dataitem = self.get_gender(patient_brain)
            dataline.append(dataitem)

            #Age
            dataitem = self.get_age(patient_brain)
            dataline.append(dataitem)

            #AgeType
            dataitem = self.get_agetype(patient_brain)
            dataline.append(dataitem)

            # Facility Province
            dataitem = self.get_facility_province(ar_brain)
            dataline.append(dataitem)

            # Facility District
            dataitem = self.get_facility_district(ar_brain)
            dataline.append(dataitem)

            # Facility
            dataitem = self.get_client_name(ar_brain)
            dataline.append(dataitem)

            # Date of Collection - Onset
            dataitem = self.get_date_of_collection(ar_brain)
            dataline.append(dataitem)

            # Date Reporting
            dataitem = self.get_date_of_dispatch(ar_brain)
            dataline.append(dataitem)

            # Specimen Collected
            dataitem = self.get_date_of_collection(ar_brain)
            dataline.append(dataitem)

            # Date of Collection - Onset
            dataitem = self.get_date_of_collection(ar_brain)
            dataline.append(dataitem)

            # Specimen Type
            dataitem = self.get_specimentype(ar_brain)
            dataline.append(dataitem)

            # Date of Dispatch
            dataitem = self.get_date_of_dispatch(ar_brain)
            dataline.append(dataitem)

            # Date of Receiving
            dataitem = self.get_date_of_receiving(ar_brain)
            dataline.append(dataitem)

            # Date of Publication
            dataitem = self.get_date_published(analysis)
            dataline.append(dataitem)

            # Condition of Specimen
            #dataitem = self.get_date_published(analysis)
            #dataline.append(dataitem)

            # Comment
            #dataitem = self.get_date_published(analysis)
            ##dataline.append(dataitem)

            # Sex
            #dataitem = self.get_patient_sex(patient_brain)
            #dataline.append(dataitem)

            # Date Of Birth
            #dataitem = self.get_patient_dob(patient_brain)
            #dataline.append(dataitem)

            # Date of Testing
            #dataitem = self.get_date_of_testing(analysis)
            #dataline.append(dataitem)

            
            #Test Result
            dataitem = self.get_result(analysis)
            dataline.append(dataitem)

            count_all += 1
            datalines.append(dataline)

        logger.info("Generating output")

        # footer data
        footlines = []
        footline = []
        footitem = {'value': _('Total'),
                    'class': 'total_label'}
        footline.append(footitem)
        footitem = {'value': count_all}
        footline.append(footitem)
        footlines.append(footline)

        self.report_content = {
            'headings': headings,
            'parms': parms,
            'formats': formats,
            'datalines': datalines,
            'footings': footlines}

        if self.request.get('output_format', '') == 'CSV':
            fieldnames = formats.get('col_heads')
            output = StringIO.StringIO()
            dw = csv.DictWriter(output, extrasaction='ignore',
                                fieldnames=fieldnames)
            dw.writerow(dict((fn, fn) for fn in fieldnames))
            for row in datalines:
                dict_row = {}
                row_idx = 0
                for column in fieldnames:
                    dict_row[column] = row[row_idx]['value']
                    row_idx += 1
                dw.writerow(dict_row)

            report_data = output.getvalue()
            output.close()
            date = datetime.datetime.now().strftime("%Y%m%d%H%M")
            setheader = self.request.RESPONSE.setHeader
            setheader('Content-Type', 'text/csv')
            setheader("Content-Disposition",
                      "attachment;filename=\"analysisresultbyclient_%s.csv"
                      "\"" %
                      date)
            self.request.RESPONSE.write(report_data)
        else:
            return {'report_title': t(headings['header']),
                    'report_data': self.template()}

    @viewcache.memoize
    def get_brain(self, uid, catalog):
        brain = self.uids_map.get(uid, None)
        if brain:
            return brain

        logger.warning("UID not found in brains map: {}".format(uid))
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
            brain = self.uids_map.get(brain_or_object_or_uid, None)
            if brain:
                return self.get_object(brain)
            return api.get_object_by_uid(brain_or_object_or_uid, default=None)
        if api.is_object(brain_or_object_or_uid):
            return api.get_object(brain_or_object_or_uid)
        return None

    def get_lab_number(self, analysis):
        try:
            """Client Sample ID"""
            return {'value': self.context.bika_setup.laboratory.getTaxNumber()}
        except:
            return {'value': 'MPH'}

    def get_firstname(self, patient):
        if not patient:
            return {'value': ''}
        return {'value': patient.getFirstname}

    def get_middlename(self, patient):
        if not patient:
            return {'value': ''}
        return {'value': patient.getMiddlename}

    def get_lastname(self, patient):
        if not patient:
            return {'value': ''}
        return {'value': patient.getSurname}

    def get_gender(self, patient):
        if not patient:
            return {'value': ''}
        return {'value': patient.getGender}

    def get_age(self, patient):
        if not patient:
            return {'value': ''}
        return {'value': patient.getAgeSplittedStr}

    def get_agetype(self, patient):
        if not patient:
            return {'value': ''}
        return {'value': patient.getAgeSplittedStr}

    def get_facility_province(self, ar):
        """Client province"""
        if not ar:
            return {'value': ''}
        return {'value': ar.getProvince}

    def get_facility_district(self, ar):
        """Client district"""
        if not ar:
            return {'value': ''}
        return {'value': ar.getDistrict}

    def get_client_name(self, ar):
        """Client name"""
        if not ar:
            return {'value': ''}
        return {'value': ar.getClientTitle}

    def get_patient_sex(self, patient):
        """Patient gender"""
        if not patient:
            return {'value': 'U'}
        genders = {'male': 'M', 'female': 'F'}
        return {'value': genders.get(patient.getGender, patient.getGender)}

    def get_patient_dob(self, patient):
        """Patient Date Of Birth"""
        if not patient:
            return {'value': ''}
        return {'value': self.ulocalized_time(patient.getBirthDate)}

    def get_date_of_collection(self, ar):
        """Patient Date Of Collection"""
        if not ar:
            return {'value': ''}
        return {'value': self.ulocalized_time(ar.getDateSampled)}

    def get_specimentype(self,ar):
        """Specimen Type"""
        if not ar:
            return {'value': ''}
        return {'value': ar.getSampleType}

    def get_date_of_receiving(self, ar):
        """Patient Date Of Receiving"""
        if not ar:
            return {'value': ''}
        return {'value': self.ulocalized_time(ar.getDateReceived)}

    def get_date_of_dispatch(self, ar):
        """Patient Date Of Publication"""
        if not ar:
            return {'value': ''}
        return {'value': self.ulocalized_time(ar.getDatePublished)}

    def get_date_of_testing(self, analysis):
        """Date Of Testing"""
        try:
            date = analysis.getResultCaptureDate
            date = self.ulocalized_time(date)
            return {'value': date}
        except:
            return {'value': ''}

    def get_result(self, analysis):
        """Result"""
        dataitem = {
            'value': analysis.getResult
                             .replace('&lt;', '<')
                             .replace('&gt;', '>')}
        return dataitem

    def get_ar_brain(self, analysis_brain):
        """
        Get the brain of the Analysis request the analysis
        is coming from.

        :param analysis_brain: The analysis brain from which
        we want to get its analysis request brain
        :return: Analysis Request brain if found else None
        """
        ar_uid = analysis_brain.getParentUID
        if not ar_uid:
            return None
        return self.get_brain(ar_uid, CATALOG_ANALYSIS_REQUEST_LISTING)

    def get_patient_brain(self, analysis_brain):
        """
        Get the brain of the patient the analysis is assigned to.

        :param analysis_brain: The analysis brain from which
        we want to get the patient it is assigned to
        :return: Patient brain if found else None
        """
        ar = self.get_ar_brain(analysis_brain)
        if not ar:
            return None
        patient_uid = ar.getPatientUID
        if not patient_uid:
            return None
        patient = self.get_brain(patient_uid, CATALOG_PATIENT_LISTING)
        return patient

    def map_uids_to_brains(self, ar_uids=None):
        """Fetches AR brains and patients and stores them in a generalist map
        where the key is the brain's uid and the value is the brain"""
        if not ar_uids:
            return
        logger.info("Mapping UIDs to brains for {} AR UIDs".format(len(ar_uids)))
        self.uids_map = dict()
        pat_uids = set()
        query = dict(UID=ar_uids)
        ar_brains = api.search(query, CATALOG_ANALYSIS_REQUEST_LISTING)
        for ar_brain in ar_brains:
            pat_uid = ar_brain.getPatientUID
            if pat_uid:
                pat_uids.add(pat_uid)
            self.uids_map[api.get_uid(ar_brain)] = ar_brain

        logger.info("Mapping UIDs to brains for {} Patient UIDs".format(len(pat_uids)))
        query = dict(UID=list(pat_uids))
        pat_brains = api.search(query, CATALOG_PATIENT_LISTING)
        self.uids_map.update({api.get_uid(pat): pat for pat in pat_brains})
