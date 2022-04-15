<?xml version="1.0"?>

<xsl:stylesheet version="3.0"
xmlns:xsl="http://www.w3.org/1999/XSL/Transform">

  <xsl:template match="/catkin_lint">
    <xsl:variable name="sum_issues">
      <xsl:value-of select="count(*)" />
    </xsl:variable>
    <xsl:choose>
      <!-- In case of any notices/warnings/errors, the test failed -->
      <xsl:when test="$sum_issues > 0">
        <testsuite name="catkin_lint" errors="0" skip="0">
          <xsl:attribute name="tests">
            <xsl:value-of select="$sum_issues" />
          </xsl:attribute>
          <xsl:attribute name="failures">
            <xsl:value-of select="$sum_issues" />
          </xsl:attribute>
          <xsl:attribute name="time">
            <xsl:value-of select="@time" />
          </xsl:attribute>
          <xsl:for-each select="*">
            <testcase>
              <xsl:attribute name="name">
                <xsl:for-each select="location/*">
                    <xsl:value-of select="current()" />
                    <xsl:if test="position() != last()">
                      <xsl:text>:</xsl:text>
                    </xsl:if>
                </xsl:for-each>
              </xsl:attribute>
              <failure>
                <xsl:attribute name="message">
                  <xsl:value-of select="text" />
                </xsl:attribute>
                <xsl:attribute name="type">
                  <xsl:value-of select="id" />
                </xsl:attribute>
              </failure>
            </testcase>
          </xsl:for-each>
        </testsuite>
      </xsl:when>
      <!-- When no notices/warnings/errors show, the test succeeded -->
      <xsl:otherwise>
        <testsuite name="catkin_lint" tests="1" errors="0" failures="0" skip="0">
          <xsl:attribute name="time">
            <xsl:value-of select="@time" />
          </xsl:attribute>
          <testcase>
            <xsl:attribute name="name">
              <xsl:value-of select="@package" />
            </xsl:attribute>
          </testcase>
        </testsuite>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>
</xsl:stylesheet>
