#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Fetch ELB statistics of cloudwatch.
"""

import datetime

from boto.ec2 import cloudwatch

from blackbird.plugins import base


class ConcreteJob(base.JobBase):

    def __init__(self, options, queue=None, logger=None):
        super(ConcreteJob, self).__init__(options, queue, logger)
        self.metrics_config = [
            {'HealthyHostCount': 'Maximum'},
            {'UnhealthyHostCount': 'Maximum'},
            {'RequestCount': 'Sum'},
            {'Latency': 'Maximum'},
            {'Latency': 'Minimum'},
            {'Latency': 'Average'},
            {'HTTPCode_ELB_4XX': 'Sum'},
            {'HTTPCode_ELB_5XX': 'Sum'},
            {'HTTPCode_Backend_2XX': 'Sum'},
            {'HTTPCode_Backend_3XX': 'Sum'},
            {'HTTPCode_Backend_4XX': 'Sum'},
            {'HTTPCode_Backend_5XX': 'Sum'},
            {'BackendConnectionErrors': 'Sum'},
            {'SpilloverCount': 'Sum'},
        ]

    def _enqueue(self, item):
        self.queue.put(item, block=False)
        self.logger.debug(
            'Inseted to queue {key}:{value}'
            ''.format(
                key=item.key,
                value=item.value
            )
        )

    def _create_connection(self):
        conn = cloudwatch.connect_to_region(
            self.options.get('region_name'),
            aws_access_key_id=self.options.get(
                'aws_access_key_id'
            ),
            aws_secret_access_key=self.options.get(
                'aws_secret_access_key'
            )
        )
        return conn

    def _fetch_statistics(self):
        conn = self._create_connection()
        result = dict()

        period = self.options.get('interval', 300)
        if period <= 60:
            period = 60
            delta_seconds = 120
        else:
            delta_seconds = period
        end_time = datetime.datetime.utcnow()
        start_time = end_time - datetime.timedelta(
            seconds=delta_seconds
        )
        dimensions = {
            'LoadBalancerName': self.options.get('load_balancer_name'),
            'AvailabilityZone': self.options.get('availability_zone')
        }

        for entry in self.metrics_config:
            for metric_name, statistics in entry.items():
                stat = conn.get_metric_statistics(
                    period=period,
                    start_time=start_time,
                    end_time=end_time,
                    metric_name=metric_name,
                    namespace='AWS/ELB',
                    statistics=statistics,
                    dimensions=dimensions
                )
                key = '{0}.{1}'.format(
                    metric_name,
                    statistics
                )
                if len(stat) > 0:
                    result[key] = stat[0][statistics]
                else:
                    result[key] = None

        conn.close()
        return result

    def build_items(self):
        """
        Main loop.
        """
        raw_items = self._fetch_statistics()
        hostname = self.options.get('hostname')

        for key, raw_value in raw_items.iteritems():
            if raw_value is None:
                value = 0
            else:
                value = raw_value

            item = ELBItem(
                key=key,
                value=value,
                host=hostname
            )
            self._enqueue(item)


class Validator(base.ValidatorBase):
    """
    Validate configuration object.
    """

    def __init__(self):
        self.__spec = None

    @property
    def spec(self):
        self.__spec = (
            "[{0}]".format(__name__),
            "region_name = string()",
            "aws_access_key_id = string()",
            "aws_secret_access_key = string()",
            "aws_region_name = string(default=us-east-1)",
            "load_balancer_name = string()",
            "availability_zone = string()",
            "hostname = string()"
        )
        return self.__spec


class ELBItem(base.ItemBase):
    """
    Enqueued item.
    """

    def __init__(self, key, value, host):
        super(ELBItem, self).__init__(key, value, host)

        self.__data = dict()
        self._generate()

    @property
    def data(self):
        """
        Dequeued data.
        """
        return self.__data

    def _generate(self):
        self.__data['key'] = 'cloudwatch.elb.{0}'.format(self.key)
        self.__data['value'] = self.value
        self.__data['host'] = self.host
        self.__data['clock'] = self.clock


if __name__ == '__main__':
    import json
    OPTIONS = {
        'region_name': 'ap-northeast-1',
        'aws_access_key_id': 'YOUR_AWS_ACCESS_KEY_ID',
        'aws_secret_access_key': 'YOUR_AWS_SECRET_ACCESS_KEY',
        'load_balancer_name': 'YOUR_ELB_NAME',
        'availability_zone': 'YOUR_AVAILABILITY_ZONE',
        'interval': 3
    }
    JOB = ConcreteJob(
        options=OPTIONS
    )
    print json.dumps(JOB._fetch_statistics())
